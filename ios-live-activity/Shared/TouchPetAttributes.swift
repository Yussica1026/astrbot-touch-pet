import ActivityKit

struct TouchPetAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var status: String
        var lastGesture: String?
    }

    var petName: String
    var symbol: String
}

