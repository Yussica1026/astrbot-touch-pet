import Foundation

enum TouchPetConfiguration {
    static let appGroup = "group.io.github.astrbot.touchpet"
    static let defaults = UserDefaults(suiteName: appGroup)!

    static var serverURL: String {
        defaults.string(forKey: "serverURL")?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    static var pairToken: String {
        defaults.string(forKey: "pairToken")?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }
}

