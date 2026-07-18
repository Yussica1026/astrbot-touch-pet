# iOS Live Activity / Dynamic Island

这是 AstrBot Touch Pet 的 iOS 17+ 原生公开版，使用 ActivityKit、WidgetKit、SwiftUI 与 App Intents。

它可以在锁屏实时活动和支持设备的灵动岛中显示桌宠状态，并通过按钮向现有 `/api/touch` 后端发送触摸信号。它不能像 Android 悬浮窗一样自由覆盖其他 App。

## Build

需要 macOS、Xcode、Apple 开发签名和 [XcodeGen](https://github.com/yonaskolb/XcodeGen)：

```bash
cd ios-live-activity
xcodegen generate
open AstrBotTouchPet.xcodeproj
```

在 Xcode 中：

1. 为 App 与 Widget Extension 选择自己的 Team。
2. 将两个 Bundle ID 改成自己的唯一值。
3. 将两个 entitlements 和 `TouchPetConfiguration.swift` 中的 App Group 改成自己的唯一 App Group。
4. 为两个 target 启用相同的 App Groups capability。
5. 使用真机测试 Live Activities 和 Dynamic Island。

配置与密钥保存在共享 App Group 中，不应写入源码或提交仓库。公网服务器应使用 HTTPS。

