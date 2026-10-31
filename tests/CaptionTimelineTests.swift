import Foundation

@main
enum CaptionTimelineTests {
    static func expect(_ condition: @autoclosure () -> Bool, _ description: String) {
        precondition(condition(), description)
    }

    static func rejects(_ description: String, _ operation: () throws -> Void) {
        do {
            try operation()
            preconditionFailure("Expected rejection: \(description)")
        } catch { }
    }

    static func message(_ epoch: UInt64 = 1, _ offset: Int64 = 0,
                        _ cues: [CaptionCue]) -> CaptionMessage {
        CaptionMessage(epoch: epoch, offset: offset, captions: cues)
    }

    static func cue(_ start: Int64, _ end: Int64, _ text: String = "Hello there") -> CaptionCue {
        CaptionCue(start: start, end: end, text: text)
    }

    static func main() throws {
        let encoded = Data(#"{"type":"visemes","epoch":2,"offset":24000,"cues":[],"captions":[[0,12000,"Hello there"],[12000,24000,"How are you?"]]}"#.utf8)
        let decoded = try JSONDecoder().decode(CaptionMessage.self, from: encoded)
        var timeline = CaptionTimeline()
        try timeline.append(decoded)
        expect(timeline.epoch == 2, "First message adopts its epoch")
        expect(timeline.text(at: 23_999) == nil, "Offset delays the first caption")
        expect(timeline.text(at: 24_000) == "Hello there", "Start is inclusive")
        expect(timeline.text(at: 35_999) == "Hello there", "Caption remains until its end")
        expect(timeline.text(at: 36_000) == "How are you?", "Adjacent caption replaces at exact endpoint")
        expect(timeline.text(at: 48_000) == nil, "End is exclusive")
        expect(timeline.cues.isEmpty, "Consumed captions are removed")

        try timeline.append(message(2, 48_000, [cue(0, 10), cue(20, 30, "After silence")]))
        expect(timeline.text(at: 48_010) == nil, "Silence hides captions")
        expect(timeline.text(at: 48_020) == "After silence", "Caption resumes after a gap")
        try timeline.append(message(1, 0, [cue(0, 100, "Stale")]))
        expect(timeline.text(at: 48_021) == "After silence", "Stale epoch is discarded")
        try timeline.append(message(3, 0, [cue(0, 100, "Fresh")]))
        expect(timeline.epoch == 3 && timeline.cues.count == 1, "New epoch replaces queued captions")
        expect(timeline.text(at: 0) == "Fresh", "New epoch restarts its clock")
        timeline.reset(4)
        expect(timeline.epoch == 4 && timeline.text(at: 0) == nil, "Flush clears text and retains epoch")
        try timeline.append(message(3, 0, [cue(0, 100, "Old after flush")]))
        expect(timeline.cues.isEmpty, "Flush prevents a late old epoch from reappearing")

        rejects("negative offset") { try timeline.append(message(4, -1, [cue(0, 10)])) }
        rejects("negative cue start") { try timeline.append(message(4, 0, [cue(-1, 10)])) }
        rejects("empty interval") { try timeline.append(message(4, 0, [cue(10, 10)])) }
        rejects("backwards interval") { try timeline.append(message(4, 0, [cue(10, 9)])) }
        rejects("local duration exceeds 120 seconds") {
            try timeline.append(message(4, 0, [cue(0, 2_880_001)]))
        }
        rejects("local overlap") { try timeline.append(message(4, 0, [cue(0, 10), cue(9, 20)])) }
        rejects("unordered cues") { try timeline.append(message(4, 0, [cue(10, 20), cue(0, 5)])) }
        rejects("empty text") { try timeline.append(message(4, 0, [cue(0, 10, " \n\t")])) }
        rejects("161 unicode scalars") {
            try timeline.append(message(4, 0, [cue(0, 10, String(repeating: "🙂", count: 161))]))
        }
        rejects("overflowing offset") {
            try timeline.append(message(4, Int64.max, [cue(0, 1)]))
        }
        rejects("overflowing start and end") {
            try timeline.append(message(4, Int64.max - 5, [cue(10, 20)]))
        }
        rejects("unicode scalar limit counts combining marks") {
            try timeline.append(message(4, 0, [cue(0, 10, "e" + String(repeating: "\u{301}", count: 160))]))
        }
        expect(timeline.cues.isEmpty, "Invalid batches make no partial changes")
        try timeline.append(message(4, 0, [cue(0, 2_880_000, String(repeating: "🙂", count: 160))]))
        expect(timeline.cues.count == 1, "Maximum duration and text length are accepted")
        rejects("absolute overlap across messages") {
            try timeline.append(message(4, 10, [cue(0, 20)]))
        }
        rejects("malformed future epoch does not flush valid captions") {
            try timeline.append(message(5, 0, [cue(0, 5), cue(4, 20)]))
        }
        expect(timeline.epoch == 4 && timeline.cues.count == 1, "Rejected future batch preserves old timeline")

        let batch = (0..<512).map { cue(Int64($0 * 2), Int64($0 * 2 + 1)) }
        timeline.reset(6)
        rejects("513 message cues") { try timeline.append(message(6, 0, batch + [cue(1_024, 1_025)])) }
        try timeline.append(message(6, 0, batch))
        try timeline.append(message(6, 1_024, batch))
        expect(timeline.cues.count == 1_024, "Queue accepts its exact limit")
        rejects("queue overflow") { try timeline.append(message(6, 2_048, [cue(0, 1)])) }
        expect(timeline.cues.count == 1_024, "Overflow leaves queue unchanged")
        expect(timeline.text(at: 2_048) == nil, "Advancing beyond audio clears old queue")
        try timeline.append(message(6, 2_048, batch))
        expect(timeline.cues.count == 512, "Consumed capacity is reusable")
        try timeline.append(message(7, 0, []))
        expect(timeline.epoch == 7 && timeline.cues.isEmpty, "Empty future epoch also flushes")
        try timeline.append(message(UInt64.max, Int64.max - 10, [cue(0, 10, "Largest clock")]))
        expect(timeline.text(at: Int64.max - 1) == "Largest clock", "Largest valid sample offset stays exact")
        expect(timeline.text(at: Int64.max) == nil, "Largest sample endpoint expires safely")
        timeline.reset()
        expect(timeline.epoch == 0 && timeline.cues.isEmpty, "Reconnect can reset the entire timeline")

        for badJSON in [
            #"{"epoch":1,"offset":0,"captions":[[0,1,"ok","extra"]]}"#,
            #"{"epoch":1,"offset":0,"captions":[[0,1]]}"#,
            #"{"epoch":1,"offset":0,"captions":[[0,1,null]]}"#,
            #"{"epoch":1,"offset":0,"captions":[[0.5,1,"fraction"]]}"#,
            #"{"epoch":1,"offset":0.5,"captions":[]}"#,
            #"{"epoch":1.5,"offset":0,"captions":[]}"#,
            #"{"epoch":-1,"offset":0,"captions":[]}"#,
            #"{"epoch":18446744073709551616,"offset":0,"captions":[]}"#,
            #"{"epoch":1,"offset":9223372036854775808,"captions":[]}"#,
            #"{"epoch":1,"offset":0,"captions":[[false,1,"boolean"]]}"#,
            #"{"epoch":1,"offset":0,"captions":[[0,1,42]]}"#
        ] {
            rejects("malformed wire data") {
                _ = try JSONDecoder().decode(CaptionMessage.self, from: Data(badJSON.utf8))
            }
        }
        print("CaptionTimelineTests passed (offsets, boundaries, gaps, epochs, validation, atomicity, queue limits)")
    }
}
