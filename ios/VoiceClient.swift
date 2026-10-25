import Foundation
import AVFoundation

/// Legacy synchronous converter callback bridge. The buffer is fully initialized
/// before publication, never mutated afterward, and handed out once under a lock.
/// Remove this bridge when AVAudioConverter exposes a Sendable input API.
private final class ConverterInput: @unchecked Sendable {
    private let lock = NSLock()
    private var buffer: AVAudioPCMBuffer?
    init(_ buffer: AVAudioPCMBuffer) { self.buffer = buffer }
    func take() -> AVAudioPCMBuffer? {
        lock.lock(); defer { lock.unlock() }
        let result = buffer; buffer = nil
        return result
    }
}

/// Audio objects and socket state are actor-owned. The real-time tap copies only
/// channel-zero samples into a bounded AsyncStream; AVAudioPCMBuffer never crosses actors.
actor VoiceClient {
    struct Capture: Sendable { let samples: Data; let rate: Double; let frames: UInt32 }
    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var sendTask: Task<Void, Never>?
    private var continuation: AsyncStream<Capture>.Continuation?
    private var converter: AVAudioConverter?
    private var converterRate: Double = 0
    private var epoch: UInt64 = 0
    private var playbackGeneration: UInt64 = 0
    private var pendingFrames = 0
    private var scheduledFrames: Int64 = 0
    private var playbackBase: Int64 = 0
    private var timeline = VisemeTimeline()
    private var animationTask: Task<Void, Never>?
    private let mouth: @MainActor @Sendable (String) -> Void
    private var active = false
    private var tapInstalled = false
    private var attached = false
    private let state: @MainActor @Sendable (String, Bool) -> Void
    init(mouth: @escaping @MainActor @Sendable (String) -> Void = { _ in },
         state: @escaping @MainActor @Sendable (String, Bool) -> Void) {
        self.mouth = mouth; self.state = state
    }

    func start(url: URL, token: String) async {
        guard !active else { return }
        guard token.count >= 24, url.scheme == "wss" ||
                (url.scheme == "ws" && ["127.0.0.1", "localhost"].contains(url.host ?? "")) else {
            await state("Secure pairing required", false); return
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker])
            try session.setPreferredIOBufferDuration(0.01)
            try session.setActive(true)
            try engine.inputNode.setVoiceProcessingEnabled(true)
            if !attached { engine.attach(player); attached = true }
            let playback = AVAudioFormat(standardFormatWithSampleRate: 24000, channels: 1)!
            engine.connect(player, to: engine.mainMixerNode, format: playback)
            let input = engine.inputNode.outputFormat(forBus: 0)
            guard input.sampleRate > 0, input.channelCount > 0 else { throw AudioError.unavailable }
            let (stream, sink) = AsyncStream<Capture>.makeStream(bufferingPolicy: .bufferingNewest(5))
            continuation = sink
            engine.inputNode.installTap(onBus: 0, bufferSize: 960, format: input) { buffer, _ in
                guard let channel = buffer.floatChannelData?[0] else { return }
                let data = Data(bytes: channel, count: Int(buffer.frameLength) * MemoryLayout<Float>.size)
                sink.yield(Capture(samples: data, rate: buffer.format.sampleRate, frames: buffer.frameLength))
            }
            tapInstalled = true
            var request = URLRequest(url: url)
            request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
            let ws = URLSession.shared.webSocketTask(with: request)
            socket = ws; active = true; epoch = 0; pendingFrames = 0
            ws.resume()
            engine.prepare(); try engine.start(); player.play()
            await state("Listening", false)
            receiveTask = Task { [weak self] in await self?.receiveLoop() }
            animationTask = Task { [weak self] in
                while !Task.isCancelled {
                    await self?.animateMouth()
                    do { try await Task.sleep(for: .milliseconds(16)) } catch { break }
                }
            }
            sendTask = Task { [weak self] in
                for await chunk in stream {
                    if Task.isCancelled { break }
                    await self?.send(chunk)
                }
            }
        } catch { await stop(status: "Audio unavailable") }
    }

    private func send(_ chunk: Capture) async {
        guard active, let ws = socket else { return }
        do {
            let sourceFormat = AVAudioFormat(standardFormatWithSampleRate: chunk.rate, channels: 1)!
            let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true)!
            if converter == nil || converterRate != chunk.rate {
                converter = AVAudioConverter(from: sourceFormat, to: targetFormat); converterRate = chunk.rate
            }
            guard let converter, let source = AVAudioPCMBuffer(pcmFormat: sourceFormat, frameCapacity: chunk.frames),
                  let target = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: UInt32(Double(chunk.frames)*16000/chunk.rate)+32) else { throw AudioError.unavailable }
            source.frameLength = chunk.frames
            chunk.samples.copyBytes(to: UnsafeMutableRawBufferPointer(start: source.floatChannelData![0], count: chunk.samples.count))
            let input = ConverterInput(source)
            var error: NSError?
            converter.convert(to: target, error: &error) { _, status in
                guard let buffer = input.take() else { status.pointee = .noDataNow; return nil }
                status.pointee = .haveData; return buffer
            }
            if error != nil { throw AudioError.unavailable }
            let data = Data(bytes: target.int16ChannelData![0], count: Int(target.frameLength)*2)
            // Bound each input message to at most 20 ms.
            for offset in stride(from: 0, to: data.count, by: 640) {
                guard active && !Task.isCancelled else { return }
                try await ws.send(.data(data.subdata(in: offset..<min(offset+640, data.count))))
            }
        } catch { await stop(status: "Reconnecting") }
    }

    private func receiveLoop() async {
        while active && !Task.isCancelled, let ws = socket {
            do {
                let message = try await ws.receive()
                guard active && !Task.isCancelled else { break }
                switch message {
                case .string(let text):
                    guard text.utf8.count <= 32768, let data = text.data(using: .utf8),
                          let event = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                          let type = event["type"] as? String else { throw AudioError.protocolError }
                    if type == "interrupt", let next = event["epoch"] as? UInt64 {
                        if next >= epoch { flush(next) }
                    } else if type == "visemes" {
                        let message = try JSONDecoder().decode(VisemeMessage.self, from: data)
                        if message.epoch > epoch { flush(message.epoch) }
                        try timeline.append(message)
                    } else if type == "expression" {
                        // Typed expression control is not speech. Rendering parity
                        // is separate; accepting it must not disconnect voice.
                        guard let name = event["name"] as? String,
                              ["neutral", "skeptical", "surprised", "scared", "pleased"].contains(name),
                              let duration = event["duration_ms"] as? Int,
                              (100...2500).contains(duration) else { throw AudioError.protocolError }
                    } else { throw AudioError.protocolError }
                case .data(let data): try await play(data)
                @unknown default: throw AudioError.protocolError
                }
            } catch { if !Task.isCancelled { await stop(status: "Reconnecting") }; break }
        }
    }
    private func flush(_ next: UInt64) {
        playbackGeneration &+= 1
        epoch = next; pendingFrames = 0
        scheduledFrames = 0; playbackBase = 0; timeline.reset(next)
        player.stop()
        if active { player.play() }
    }
    private func play(_ data: Data) async throws {
        guard data.count > 8, data.count <= 7688, (data.count-8)%2 == 0 else { throw AudioError.protocolError }
        let incoming = data.prefix(8).reduce(UInt64(0)) { ($0 << 8) | UInt64($1) }
        if incoming < epoch { return }
        if incoming > epoch { flush(incoming) }
        let count = (data.count-8)/2
        guard pendingFrames + count <= 5760 else { throw AudioError.queueOverflow }
        let format = AVAudioFormat(standardFormatWithSampleRate: 24000, channels: 1)!
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: UInt32(count)) else { throw AudioError.unavailable }
        buffer.frameLength = UInt32(count)
        let bytes = [UInt8](data.dropFirst(8))
        for i in 0..<count {
            let value = Int16(bitPattern: UInt16(bytes[2*i]) | UInt16(bytes[2*i+1]) << 8)
            buffer.floatChannelData![0][i] = Float(value)/32768
        }
        if pendingFrames == 0 {
            // Reset the player clock after an idle gap. Protocol offsets count
            // audio samples only, not wall time while nobody is speaking.
            player.stop(); player.play()
            playbackBase = scheduledFrames
        }
        scheduledFrames += Int64(count)
        pendingFrames += count
        let generation = playbackGeneration
        player.scheduleBuffer(buffer, completionCallbackType: .dataPlayedBack) { [weak self] _ in
            Task { await self?.played(count, epoch: incoming, generation: generation) }
        }
        await state("Listening", true)
    }
    private func played(_ count: Int, epoch completedEpoch: UInt64, generation: UInt64) async {
        guard completedEpoch == epoch, generation == playbackGeneration, active else { return }
        pendingFrames = max(0, pendingFrames-count)
        if pendingFrames == 0 { await state("Listening", false) }
    }
    private func animateMouth() async {
        guard active, pendingFrames > 0, let render = player.lastRenderTime,
              let position = player.playerTime(forNodeTime: render) else {
            await mouth("rest"); return
        }
        let sample = playbackBase + max(0, position.sampleTime)
        await mouth(timeline.shape(at: sample))
    }
    func stop(status: String = "Muted") async {
        active = false; epoch &+= 1; playbackGeneration &+= 1
        continuation?.finish(); continuation = nil
        receiveTask?.cancel(); receiveTask = nil
        sendTask?.cancel(); sendTask = nil
        animationTask?.cancel(); animationTask = nil
        socket?.cancel(with: .goingAway, reason: nil); socket = nil
        player.stop(); engine.stop(); pendingFrames = 0
        scheduledFrames = 0; playbackBase = 0; timeline.reset(epoch)
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        converter = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        await state(status, false)
        await mouth("rest")
    }
    enum AudioError: Error { case unavailable, protocolError, queueOverflow }
}
