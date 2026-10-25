import Foundation

@main struct SceneImagePacketTests {
    static func main() throws {
        let destination = try SceneImagePacket.destination(URL(string:"wss://local-mac.example:8765/voice?ignored=1")!)
        assert(destination.absoluteString == "wss://local-mac.example:8765/vision")
        for value in ["ws://192.168.1.4:8765/voice", "https://example.com/voice", "wss://user:secret@example.com/voice"] {
            do { _ = try SceneImagePacket.destination(URL(string:value)!); fatalError("Unsafe destination accepted") }
            catch { }
        }
        let jpeg = Data([0xff,0xd8,0xff,0xe0,0,0]) // Envelope fixture, not a decodable photograph.
        let packet = try SceneImagePacket.encode(jpeg:jpeg,ageMilliseconds:513)
        assert(Array(packet.prefix(4)) == [0,0,2,1])
        assert(packet.dropFirst(4) == jpeg)
        for age in [-1,1001] {
            do { _ = try SceneImagePacket.encode(jpeg:jpeg,ageMilliseconds:age); fatalError("Stale frame accepted") }
            catch { }
        }
        for bytes in [Data([1,2,3]), jpeg+Data(repeating:0,count:256_000)] {
            do { _ = try SceneImagePacket.encode(jpeg:bytes,ageMilliseconds:0); fatalError("Bad image envelope accepted") }
            catch { }
        }
        print("Synthetic iOS image envelope/security boundaries passed; not vision accuracy")
    }
}
