import UIKit

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
    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }
    override func loadView() { view = FaceView() }
}

final class FaceView: UIView {
    private var ticker: CADisplayLink?
    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        isUserInteractionEnabled = false
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
        let mouth = UIBezierPath()
        mouth.move(to: CGPoint(x: w*0.35, y: h*0.55+bob))
        mouth.addQuadCurve(to: CGPoint(x: w*0.65, y: h*0.55+bob),
                           controlPoint: CGPoint(x: w*0.50, y: h*0.68+bob))
        UIColor(red: 192/255, green: 1, blue: 231/255, alpha: 1).setStroke()
        mouth.lineWidth = w*0.025
        mouth.lineCapStyle = .round
        mouth.stroke()
    }
}
