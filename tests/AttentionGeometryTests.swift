import Foundation

@main struct AttentionGeometryTests {
    static func main() {
        let upperLeft = CGRect(x:0.1,y:0.7,width:0.2,height:0.2)
        let first = AttentionGeometry.observation(bounds:[upperLeft],capturedAt:10)
        assert(abs(first.x-0.2) < 0.001 && abs(first.y-0.2) < 0.001)
        let right = CGRect(x:0.6,y:0.4,width:0.4,height:0.4)
        let group = AttentionGeometry.observation(bounds:[upperLeft,right],capturedAt:10)
        assert(abs(group.x-0.5) < 0.001, "Must not simply follow the largest face")
        for size in [0,1,2,32,33,64] {
            let result = AttentionGeometry.observation(bounds:Array(repeating:upperLeft,count:size),capturedAt:10)
            assert(result.faces == min(32,size))
            assert(result.overflow == (size > 32))
            assert(result.observedAt == 10)
            if size == 0 { assert(result.x == 0.5 && result.y == 0.5) }
        }
        print("Synthetic iOS group coordinates and crowd overflow passed; not camera acceptance")
    }
}
