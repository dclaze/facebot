import Foundation
import QuartzCore

enum SceneImageError: Error { case invalid }

enum SceneImagePacket {
    static func destination(_ voiceURL: URL) throws -> URL {
        guard let host = voiceURL.host, voiceURL.user == nil, voiceURL.password == nil,
              voiceURL.scheme == "wss" || (voiceURL.scheme == "ws" && ["localhost","127.0.0.1"].contains(host)),
              var parts = URLComponents(url:voiceURL,resolvingAgainstBaseURL:false) else { throw SceneImageError.invalid }
        parts.path = "/vision"; parts.query = nil; parts.fragment = nil
        guard let url = parts.url else { throw SceneImageError.invalid }
        return url
    }
    static func encode(jpeg: Data, ageMilliseconds: Int) throws -> Data {
        guard (0...1000).contains(ageMilliseconds), jpeg.count <= 256_000,
              jpeg.starts(with:[0xff,0xd8,0xff]) else { throw SceneImageError.invalid }
        var age = UInt32(ageMilliseconds).bigEndian
        var packet = withUnsafeBytes(of:&age) { Data($0) }
        packet.append(jpeg)
        return packet
    }
}

/// Separate, single-flight image transport. No frame files or speech dependency.
actor SceneImageClient {
    private struct Ack: Decodable { let frames: Int; let errors: Int }
    private let request: URLRequest
    private var socket: URLSessionWebSocketTask?
    private var pending = false
    private var closed = false
    private var sequence: UInt64 = 0
    private var lastSubmission = -Double.infinity

    init(voiceURL: URL, token: String) throws {
        guard token.count >= 24 else { throw SceneImageError.invalid }
        var request = URLRequest(url:try SceneImagePacket.destination(voiceURL))
        request.setValue("Bearer " + token,forHTTPHeaderField:"Authorization")
        self.request = request
    }
    func submit(jpeg: Data, capturedAt: Double) async {
        let now = CACurrentMediaTime(), age = (now-capturedAt)*1000
        guard !closed, !pending, now-lastSubmission >= 1.5,
              age.isFinite, age >= 0, age <= 1000,
              let packet = try? SceneImagePacket.encode(jpeg:jpeg,ageMilliseconds:Int(age)) else { return }
        pending = true; lastSubmission = now; sequence &+= 1
        let current = sequence
        let ws: URLSessionWebSocketTask
        if let socket { ws = socket }
        else {
            ws = URLSession.shared.webSocketTask(with:request)
            ws.maximumMessageSize = 32768
            socket = ws; ws.resume()
        }
        let deadline = Task { [weak self] in
            do { try await Task.sleep(for:.seconds(25)) } catch { return }
            await self?.timeout(current)
        }
        defer { deadline.cancel(); if sequence == current { pending = false } }
        do {
            try await ws.send(.data(packet))
            let response = try await ws.receive()
            guard !closed, current == sequence, case .string(let text) = response,
                  text.utf8.count <= 32768 else { throw SceneImageError.invalid }
            let ack = try JSONDecoder().decode(Ack.self,from:Data(text.utf8))
            guard ack.frames >= 0, ack.errors >= 0 else { throw SceneImageError.invalid }
        } catch {
            if current == sequence { ws.cancel(with:.goingAway,reason:nil); socket = nil }
        }
    }
    private func timeout(_ current: UInt64) {
        guard sequence == current, pending else { return }
        socket?.cancel(with:.goingAway,reason:nil); socket = nil
    }
    func close() {
        closed = true; sequence &+= 1; pending = false
        socket?.cancel(with:.goingAway,reason:nil); socket = nil
    }
}
