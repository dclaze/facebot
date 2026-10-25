import Foundation

@main struct VisemeTimelineTests {
    static func message(_ text: String) throws -> VisemeMessage {
        try JSONDecoder().decode(VisemeMessage.self, from: Data(text.utf8))
    }
    static func main() throws {
        var timeline = VisemeTimeline()
        try timeline.append(message(#"{"epoch":0,"offset":100,"cues":[[0,240,"closed"],[240,480,"open"]]}"#))
        assert(timeline.shape(at: 99) == "rest")
        assert(timeline.shape(at: 100) == "closed")
        assert(timeline.shape(at: 340) == "open")
        assert(timeline.shape(at: 580) == "rest")
        timeline.reset(1)
        try timeline.append(message(#"{"epoch":0,"offset":0,"cues":[[0,240,"open"]]}"#))
        assert(timeline.shape(at: 1) == "rest", "Stale interrupted animation returned")
        for raw in [
            #"{"epoch":1,"offset":-1,"cues":[]}"#,
            #"{"epoch":1,"offset":0,"cues":[[10,1,"open"]]}"#,
            #"{"epoch":1,"offset":0,"cues":[[0,240,"script"]]}"#,
            #"{"epoch":1,"offset":9223372036854775807,"cues":[[0,240,"open"]]}"#,
            #"{"epoch":1,"offset":0,"cues":[[0,240,"open"],[100,300,"closed"]]}"#
        ] {
            do { try timeline.append(message(raw)); fatalError("Invalid cue accepted") }
            catch { }
        }
        print("Viseme timeline synthetic boundaries, stale epochs and invalid cues passed")
    }
}
