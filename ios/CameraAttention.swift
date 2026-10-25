import AVFoundation
import Vision
import QuartzCore

/// Capture/session/Vision state is confined to `queue`, including delegate calls.
/// No sample buffer crosses the queue or leaves the device. The only callback
/// payload is immutable numeric metadata. Replace this bridge with an executor-
/// bound actor when AVFoundation's delegate APIs support that isolation directly.
final class CameraAttention: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    private let queue = DispatchQueue(label: "org.facebot.attention", qos: .userInitiated)
    private let session = AVCaptureSession()
    private let request = VNDetectFaceRectanglesRequest()
    private let report: @MainActor @Sendable (AttentionObservation) -> Void
    private var configured = false
    private var running = false
    private var lastAnalysis = -Double.infinity
    private var reportPending = false

    init(report: @escaping @MainActor @Sendable (AttentionObservation) -> Void) {
        self.report = report
    }
    func start() { queue.async { [weak self] in self?.startOnQueue() } }
    func stop() {
        queue.async { [weak self] in
            guard let self else { return }
            self.running = false
            self.session.stopRunning()
        }
    }
    private func startOnQueue() {
        guard !running, AVCaptureDevice.authorizationStatus(for: .video) == .authorized else { return }
        if !configured {
            guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
                  let input = try? AVCaptureDeviceInput(device: camera) else { return }
            session.beginConfiguration()
            session.sessionPreset = .vga640x480
            let output = AVCaptureVideoDataOutput()
            output.alwaysDiscardsLateVideoFrames = true
            output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange]
            guard session.canAddInput(input), session.canAddOutput(output) else {
                session.commitConfiguration(); return
            }
            session.addInput(input); session.addOutput(output)
            output.setSampleBufferDelegate(self, queue: queue)
            if let connection = output.connection(with: .video) {
                if connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 }
                connection.automaticallyAdjustsVideoMirroring = false
                if connection.isVideoMirroringSupported { connection.isVideoMirrored = true }
            }
            session.commitConfiguration(); configured = true
        }
        lastAnalysis = -Double.infinity
        session.startRunning(); running = session.isRunning
    }
    func captureOutput(_ output: AVCaptureOutput, didOutput buffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        let now = CACurrentMediaTime()
        guard running, !reportPending, now-lastAnalysis >= 0.1 else { return }
        lastAnalysis = now
        let captured = CMSampleBufferGetPresentationTimeStamp(buffer).seconds
        guard captured.isFinite, now >= captured, now-captured < 0.5,
              let pixels = CMSampleBufferGetImageBuffer(buffer) else { return }
        do {
            try VNImageRequestHandler(cvPixelBuffer: pixels, orientation: .up).perform([request])
            guard CACurrentMediaTime()-captured < 0.5 else { return }
            let faces = request.results ?? []
            // Bounded anonymous group attention, never active-speaker inference.
            let observation = AttentionGeometry.observation(bounds: faces.map(\.boundingBox), capturedAt: captured)
            reportPending = true
            Task { @MainActor [weak self, report] in
                report(observation)
                self?.queue.async { [weak self] in self?.reportPending = false }
            }
        } catch {
            // No invented zero count on camera failure; prior evidence expires.
        }
    }
}
