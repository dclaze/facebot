import Foundation
import CoreGraphics

struct AttentionObservation: Sendable {
    let faces: Int
    let overflow: Bool
    let x: Double
    let y: Double
    let observedAt: Double
}

enum AttentionGeometry {
    /// Vision rectangles use a lower-left origin in the already upright,
    /// mirrored pixel buffer. UI coordinates use a top-left origin.
    static func observation(bounds: [CGRect], capturedAt: Double) -> AttentionObservation {
        let visible = bounds.prefix(32)
        let count = Double(max(1, visible.count))
        var sumX = 0.0, sumY = 0.0
        for box in visible {
            sumX += Double(box.midX)
            sumY += 1.0-Double(box.midY)
        }
        let x = sumX/count, y = sumY/count
        return AttentionObservation(faces: min(32, bounds.count), overflow: bounds.count > 32,
            x: bounds.isEmpty ? 0.5 : x, y: bounds.isEmpty ? 0.5 : y, observedAt: capturedAt)
    }
}
