import ActivityKit
import AppIntents
import Foundation

struct SendTouchIntent: AppIntent {
    static var title: LocalizedStringResource = "发送触摸信号"
    static var description = IntentDescription("将一次桌宠触摸发送到 AstrBot Touch Pet 服务。")
    static var openAppWhenRun = false

    @Parameter(title: "手势") var gesture: String

    init() {}
    init(gesture: String) { self.gesture = gesture }

    func perform() async throws -> some IntentResult {
        let base = TouchPetConfiguration.serverURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: "\(base)/api/touch"), !TouchPetConfiguration.pairToken.isEmpty else {
            throw TouchPetError.missingConfiguration
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(TouchPetConfiguration.pairToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "gesture": gesture,
            "request_id": UUID().uuidString
        ])

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw TouchPetError.deliveryFailed
        }

        let labels = ["tap": "轻戳", "long_press": "摸摸", "drag": "拉一拉", "double_tap": "戳两下"]
        let content = ActivityContent(
            state: TouchPetAttributes.ContentState(status: "已送达", lastGesture: labels[gesture] ?? gesture),
            staleDate: Date().addingTimeInterval(30)
        )
        for activity in Activity<TouchPetAttributes>.activities {
            await activity.update(content)
        }
        return .result()
    }
}

enum TouchPetError: Error {
    case missingConfiguration
    case deliveryFailed
}

