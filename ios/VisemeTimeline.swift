import Foundation

struct VisemeCue: Decodable, Sendable {
    let start: Int64
    let end: Int64
    let shape: String
    init(from decoder: Decoder) throws {
        var values = try decoder.unkeyedContainer()
        start = try values.decode(Int64.self)
        end = try values.decode(Int64.self)
        shape = try values.decode(String.self)
        guard values.isAtEnd else { throw TimelineError.invalid }
    }
}
struct VisemeMessage: Decodable, Sendable {
    let epoch: UInt64
    let offset: Int64
    let cues: [VisemeCue]
}
enum TimelineError: Error { case invalid }

struct VisemeTimeline: Sendable {
    static let shapes: Set<String> = ["rest", "closed", "open", "wide", "round", "pucker", "teeth", "tongue", "narrow"]
    private var cues: [(Int64, Int64, String)] = []
    private(set) var epoch: UInt64 = 0
    mutating func reset(_ epoch: UInt64) { self.epoch = epoch; cues.removeAll(keepingCapacity: true) }
    mutating func append(_ message: VisemeMessage) throws {
        if message.epoch < epoch { return }
        guard message.epoch == epoch, message.offset >= 0,
              message.offset <= Int64.max - 480_000, message.cues.count <= 512,
              cues.count + message.cues.count <= 1024 else { throw TimelineError.invalid }
        var previous: Int64 = -1
        for cue in message.cues {
            guard cue.start >= 0, cue.start >= previous, cue.end > cue.start,
                  cue.end <= 480_000, Self.shapes.contains(cue.shape) else { throw TimelineError.invalid }
            previous = cue.end
        }
        cues += message.cues.map { ($0.start + message.offset, $0.end + message.offset, $0.shape) }
    }
    mutating func shape(at sample: Int64) -> String {
        cues.removeAll { $0.1 <= sample }
        return cues.first { $0.0 <= sample && sample < $0.1 }?.2 ?? "rest"
    }
}
