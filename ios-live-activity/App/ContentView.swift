import ActivityKit
import SwiftUI

struct ContentView: View {
    @State private var serverURL = TouchPetConfiguration.serverURL
    @State private var pairToken = TouchPetConfiguration.pairToken
    @State private var message = "配置后启动灵动岛桌宠"

    var body: some View {
        NavigationStack {
            Form {
                Section("AstrBot Touch Pet") {
                    TextField("https://example.com:8443", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    SecureField("桌宠配对令牌", text: $pairToken)
                    Button("保存配置") { save() }
                }

                Section("Live Activity") {
                    Button("启动灵动岛桌宠") { startActivity() }
                    Button("结束全部桌宠活动", role: .destructive) { endActivities() }
                    Text(message).font(.footnote).foregroundStyle(.secondary)
                }

                Section("说明") {
                    Text("支持灵动岛的设备会显示紧凑、最小和展开布局；其他兼容设备显示锁屏实时活动。")
                    Text("公网服务请使用 HTTPS。")
                }
            }
            .navigationTitle("Touch Pet")
        }
    }

    private func save() {
        TouchPetConfiguration.defaults.set(serverURL.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "serverURL")
        TouchPetConfiguration.defaults.set(pairToken.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "pairToken")
        message = "配置已保存"
    }

    private func startActivity() {
        save()
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            message = "请先在系统设置中允许实时活动"
            return
        }
        do {
            let attributes = TouchPetAttributes(petName: "Touch Pet", symbol: "🐾")
            let content = ActivityContent(
                state: TouchPetAttributes.ContentState(status: "正在陪着你", lastGesture: nil),
                staleDate: nil
            )
            _ = try Activity.request(attributes: attributes, content: content, pushType: nil)
            message = "灵动岛桌宠已启动"
        } catch {
            message = "启动失败：\(error.localizedDescription)"
        }
    }

    private func endActivities() {
        Task {
            for activity in Activity<TouchPetAttributes>.activities {
                await activity.end(nil, dismissalPolicy: .immediate)
            }
            message = "实时活动已结束"
        }
    }
}

