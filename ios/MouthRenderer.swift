import UIKit

/// Same nine articulations as Android. Finite transitions follow audio cues;
/// there is no periodic talking oscillator.
@MainActor final class MouthRenderer {
    private static let poses: [[CGFloat]] = [
        [0.31,0,0.022,0,0,0,0,0.012], [0.27,0,0.008,0,0,0,0,0.004],
        [0.28,0.108,0.009,0.25,0.72,0.25,0,0.006], [0.35,0.047,0.019,0,1,0,0,0.009],
        [0.18,0.100,0,1,0,0,0,0.002], [0.16,0.059,0,1,0,0,0,0.002],
        [0.28,0.027,0.010,0.10,1,0,1,0.006], [0.28,0.053,0.010,0.15,0.75,1,0,0.005],
        [0.30,0.028,0.013,0,0.90,0,0,0.007]
    ]
    private static let names = ["rest","closed","open","wide","round","pucker","teeth","tongue","narrow"]
    private var pose = poses[0]
    private var start = poses[0]
    private var current = 0
    private var changed: Double = 0
    private let mint = UIColor(red: 94/255, green: 235/255, blue: 184/255, alpha: 1)
    private let ice = UIColor(red: 206/255, green: 1, blue: 238/255, alpha: 1)

    func draw(shape: String, time: Double, size: CGSize, bob: CGFloat) {
        let u = CGFloat(min(1, max(0, (time-changed)/(current <= 1 ? 0.030 : 0.045))))
        let blend = u*u*(3-2*u)
        pose = zip(start, Self.poses[current]).map { $0 + ($1-$0)*blend }
        let next = Self.names.firstIndex(of: shape) ?? 0
        if next != current { start = pose; current = next; changed = time }
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState(); defer { context.restoreGState() }
        context.translateBy(x: 0, y: bob)
        context.scaleBy(x: size.width, y: size.height)
        let p = pose, w=p[0], a=p[1], smile=p[2], round=p[3], lift=p[7]
        let l=0.5-w/2, r=0.5+w/2, y: CGFloat=0.574, rightY=y-lift
        let leftCorner=y+a*0.28, rightCorner=rightY+a*0.28, mid=y-lift/2+smile*0.75
        let edge=w*0.10*(1-round)*(1-min(1,a/0.070))
        let outline=UIBezierPath()
        outline.move(to: CGPoint(x:l,y:leftCorner))
        outline.addCurve(to: CGPoint(x:0.5,y:mid-a*0.12), controlPoint1: CGPoint(x:l+edge,y:y+smile*0.45-a*0.12), controlPoint2: CGPoint(x:0.5-w*0.18,y:mid-a*0.12))
        outline.addCurve(to: CGPoint(x:r,y:rightCorner), controlPoint1: CGPoint(x:0.5+w*0.18,y:mid-a*0.12), controlPoint2: CGPoint(x:r-edge,y:rightY+smile*0.45-a*0.12))
        outline.addCurve(to: CGPoint(x:0.5,y:mid+a*0.94), controlPoint1: CGPoint(x:r-edge,y:rightY+smile*0.45+a*(0.45+0.38*round)), controlPoint2: CGPoint(x:0.5+w*0.18,y:mid+a*0.94))
        outline.addCurve(to: CGPoint(x:l,y:leftCorner), controlPoint1: CGPoint(x:0.5-w*0.18,y:mid+a*0.94), controlPoint2: CGPoint(x:l+edge,y:y+smile*0.45+a*(0.45+0.38*round)))
        outline.close()
        UIColor(red:2/255,green:13/255,blue:12/255,alpha:1).setFill(); outline.fill()
        context.saveGState(); outline.addClip()
        let visibility=min(1,a/0.018)
        let teeth=UIBezierPath()
        teeth.move(to:CGPoint(x:l+w*0.10,y:y-0.025))
        teeth.addLine(to:CGPoint(x:r-w*0.10,y:rightY-0.025))
        teeth.addLine(to:CGPoint(x:r-w*0.10,y:rightY+0.007))
        teeth.addCurve(to:CGPoint(x:l+w*0.10,y:y+0.007),controlPoint1:CGPoint(x:r-w*0.22,y:rightY+smile+0.012*p[4]),controlPoint2:CGPoint(x:l+w*0.22,y:y+smile+0.012*p[4]))
        teeth.close(); ice.withAlphaComponent(visibility*min(1,p[4]*2)).setFill(); teeth.fill()
        let bite=UIBezierPath()
        bite.move(to:CGPoint(x:l,y:y+a+0.025))
        bite.addLine(to:CGPoint(x:l,y:y+a*0.85))
        bite.addCurve(to:CGPoint(x:r,y:rightY+a*0.85),controlPoint1:CGPoint(x:l+w*0.28,y:y+a*0.28),controlPoint2:CGPoint(x:r-w*0.24,y:rightY+a*0.28))
        bite.addLine(to:CGPoint(x:r,y:rightY+a+0.025)); bite.close()
        UIColor(red:70/255,green:164/255,blue:137/255,alpha:p[6]*visibility).setFill(); bite.fill()
        let base=y+a+smile/2, tip=base-a*(0.12+0.55*p[5])
        let tongue=UIBezierPath()
        tongue.move(to:CGPoint(x:0.5-w*0.25,y:base+0.015))
        tongue.addCurve(to:CGPoint(x:0.5+w*0.22,y:base+0.015),controlPoint1:CGPoint(x:0.5-w*0.23,y:tip),controlPoint2:CGPoint(x:0.5+w*0.18,y:tip-0.005))
        tongue.close(); UIColor(red:66/255,green:137/255,blue:117/255,alpha:0.82*p[5]*visibility).setFill(); tongue.fill()
        context.restoreGState()
        mint.setStroke(); outline.lineWidth=0.0065; outline.lineJoinStyle = .round; outline.stroke()
        if a < 0.003 {
            ice.setStroke(); outline.lineWidth=0.008; outline.stroke()
        }
    }
}
