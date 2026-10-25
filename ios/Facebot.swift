import UIKit
import AVFoundation

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = FaceController()
        window.makeKeyAndVisible()
        self.window = window
        application.isIdleTimerDisabled = true
        return true
    }
}

final class FaceController: UIViewController {
    private struct Pairing: Decodable { let url: URL; let token: String; let name: String? }
    private var pairing: Pairing?
    private var voice: VoiceClient?
    private var connectionTask: Task<Void, Never>?
    private var generation = 0
    private var foreground = false
    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }
    override func loadView() { view = FaceView() }
    override func viewDidLoad() {
        super.viewDidLoad()
        if let url = Bundle.main.url(forResource: "local-config", withExtension: "json"),
           let data = try? Data(contentsOf: url), data.count <= 8192 {
            pairing = try? JSONDecoder().decode(Pairing.self, from: data)
        }
        (view as? FaceView)?.characterName = pairing?.name ?? "Boo"
        NotificationCenter.default.addObserver(self, selector: #selector(activate),
            name: UIApplication.didBecomeActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(deactivate),
            name: UIApplication.willResignActiveNotification, object: nil)
    }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if UIApplication.shared.applicationState == .active { activate() }
    }
    @objc private func activate() {
        guard !foreground else { return }
        foreground = true
        connect()
    }
    @objc private func deactivate() {
        foreground = false; generation += 1
        connectionTask?.cancel(); connectionTask = nil
        let old = voice; voice = nil
        (view as? FaceView)?.status = "Muted"
        (view as? FaceView)?.speaking = false
        connectionTask = Task { await old?.stop() }
    }
    private func connect() {
        guard foreground, voice == nil, let pairing else { return }
        generation += 1
        let current = generation
        let previous = connectionTask
        connectionTask = Task { [weak self] in
            await previous?.value
            let allowed = await AVAudioApplication.requestRecordPermission()
            guard let self, self.foreground, self.generation == current, !Task.isCancelled else { return }
            guard allowed else { (self.view as? FaceView)?.status = "Microphone permission needed"; return }
            (self.view as? FaceView)?.status = "Connecting"
            let client = VoiceClient(mouth: { [weak self] shape in
                guard let self, self.foreground, self.generation == current else { return }
                (self.view as? FaceView)?.mouthShape = shape
            }) { [weak self] status, speaking in
                guard let self, self.foreground, self.generation == current else { return }
                (self.view as? FaceView)?.status = status
                (self.view as? FaceView)?.speaking = speaking
                if status == "Reconnecting" { self.retry(current) }
            }
            self.voice = client
            await client.start(url: pairing.url, token: pairing.token)
        }
    }
    private func retry(_ current: Int) {
        voice = nil
        connectionTask = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(1.5)) } catch { return }
            guard let self, self.foreground, self.generation == current else { return }
            self.connectionTask = nil
            self.connect()
        }
    }
}

final class FaceView: UIView {
    private var ticker: CADisplayLink?
    var characterName = "Boo"
    var status = "Pairing required"
    var speaking = false
    var mouthShape = "rest"
    private let mouthRenderer = MouthRenderer()
    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        isUserInteractionEnabled = false
        #if targetEnvironment(simulator)
        // Synthetic artwork preview only; never enables capture or pairing.
        let arguments = ProcessInfo.processInfo.arguments
        if let index = arguments.firstIndex(of: "--mouth-preview"), index+1 < arguments.count,
           VisemeTimeline.shapes.contains(arguments[index+1]) {
            mouthShape = arguments[index+1]; speaking = true
        }
        #endif
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }
    override func didMoveToWindow() {
        super.didMoveToWindow()
        ticker?.invalidate()
        ticker = nil
        if window != nil {
            let link = CADisplayLink(target: self, selector: #selector(tick))
            link.add(to: .main, forMode: .common)
            ticker = link
        }
    }
    @objc private func tick() { setNeedsDisplay() }
    override func draw(_ rect: CGRect) {
        let w = bounds.width, h = bounds.height
        let seconds = CACurrentMediaTime()
        let bob = sin(seconds * 1.4) * h * 0.008
        let blink = seconds.truncatingRemainder(dividingBy: 4.7) < 0.13 ? 0.012 : 0.09
        UIColor(red: 192/255, green: 1, blue: 231/255, alpha: 1).setFill()
        for x in [0.15, 0.60] {
            UIBezierPath(ovalIn: CGRect(x: w*x, y: h*(0.37-blink)+bob,
                                       width: w*0.25, height: h*blink*2)).fill()
        }
        mouthRenderer.draw(shape: speaking ? mouthShape : "rest", time: seconds,
                           size: bounds.size, bob: bob)
        let color = UIColor(red: 192/255, green: 1, blue: 231/255, alpha: 1)
        for (text, y, size) in [(characterName, 0.77, 0.065), (status, 0.82, 0.025)] {
            let attributes: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: w*size), .foregroundColor: color]
            let string = text as NSString
            let extent = string.size(withAttributes: attributes)
            string.draw(at: CGPoint(x: (w-extent.width)/2, y: h*y-extent.height), withAttributes: attributes)
        }
    }
}
