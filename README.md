# AstrBot Touch Pet

[![Tests](https://github.com/Yussica1026/astrbot-touch-pet/actions/workflows/tests.yml/badge.svg)](https://github.com/Yussica1026/astrbot-touch-pet/actions/workflows/tests.yml)

一个手机优先、可自由换皮的 AstrBot 触摸桌宠 PWA。

用户可以单击、长按、拖拽、双击桌宠，也可以在页面底部发送文字。服务器先把原始触摸或文字零 token 转发到目标会话，再交给 AstrBot 中的 AI 自行生成回应。

> 本项目源自一只私人专属桌宠的实现。公开仓库不包含该私人角色的图片、称呼、会话配置或其他个人资料，只提供可复用的通用模板。

本仓库提供三个 AstrBot 专用公开客户端：

| 版本 | 目录 | 适用场景 | 跨 App 能力 |
|---|---|---|---|
| Web/PWA | 根目录 | iPhone 13 Pro Max 等没有灵动岛的设备，以及快速网页安装 | 只能在 PWA 页面内自由拖动 |
| Android Overlay | `android/` | Android 原生悬浮桌宠 | 可显示在其他 App 上层并全屏拖动 |
| iOS Live Activity | `ios-live-activity/` | iOS 17+、支持灵动岛的 iPhone | 显示在灵动岛和锁屏，由系统管理位置 |

## Credits

- 设计：示例用户、示例角色甲
- 项目整理、开发与文档：示例助手（示例助手）

## Features

- 手机端 PWA，可添加到主屏幕
- 单击、长按、拖拽、双击四种互斥手势
- 桌宠可拖到屏幕任意位置，松手停留并在本机保存位置
- 屏幕旋转或尺寸变化时自动限制在可见区域，避免桌宠被拖丢
- 宠物名称、图片、提示文字与触摸信号均可替换
- FastAPI 单端口提供静态页面和触摸 API
- 页面内文字输入与 `POST /api/chat`
- 从 `data_v4.db` 的 `conversations` 表读取最近 10 条 QQ 上下文
- 对接 AstrBot `/api/v1/chat`
- 兼容 AstrBot 4.22.3 的 SSE `type=plain` 文本事件，并过滤工具调用 `chain_type`
- 触摸和文字先通过主动消息零 token 通知目标会话
- 通过 `/api/v1/im/message` 主动发送消息
- 30 秒冷却、请求 ID 幂等、每小时限流
- 配对令牌与服务端 API Key 分离
- 不在日志中记录密钥、配对令牌或 AI 回复正文

## How it works

```text
触摸桌宠
   ↓
POST /api/touch
   ↓
FastAPI 服务
   ↓
AstrBot /api/v1/chat
   ↓
目标 AI 自行生成回复
   ↓
AstrBot /api/v1/im/message
   ↓
指定的 QQ / IM 会话
```

前端只发送触摸类型。回复内容由 AstrBot 中的目标 AI 根据自身人格、状态和记忆决定，模板不提供固定台词。

## Requirements

- Python 3.10+
- AstrBot 4.22.3 或经过验证的兼容版本
- 已启用 AstrBot HTTP API
- 具有 `chat` 与 `im` 权限的 API Key
- 支持主动发送消息的 AstrBot 消息平台适配器

## Installation

```bash
git clone https://github.com/Yussica1026/astrbot-touch-pet.git
cd astrbot-touch-pet
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## Configuration

### Server configuration

编辑私有的 `.env`：

```dotenv
ASTRBOT_BASE_URL=http://127.0.0.1:6185
ASTRBOT_API_KEY=YOUR_ASTRBOT_API_KEY
ASTRBOT_TARGET_UMO=platform_id:FriendMessage:session_id
ASTRBOT_CHAT_USERNAME=touch_pet_user
# 留空：触摸事件注入目标聊天的同一个上下文
ASTRBOT_CHAT_SESSION_ID=

TOUCH_PET_PAIR_TOKEN=REPLACE_WITH_A_LONG_RANDOM_TOKEN
COOLDOWN_SECONDS=30
MAX_REQUESTS_PER_HOUR=60
ASTRBOT_TIMEOUT_SECONDS=120
ASTRBOT_CONTEXT_DB_PATH=/AstrBot/data/data_v4.db
ASTRBOT_CONTEXT_LIMIT=10
```

早期私人原型使用的 `STONE_DOG_PAIR_TOKEN` 仍可兼容读取；新项目请统一使用 `TOUCH_PET_PAIR_TOKEN`。

生成随机配对令牌：

```bash
python scripts/generate_pair_token.py
```

### Get the complete UMO

在目标私聊中发送：

```text
/sid
```

将 AstrBot 返回的完整 UMO 原样写入 `ASTRBOT_TARGET_UMO`。

不要只填写类似 `FriendMessage_123456` 的旧式会话标识。旧标识可能让 `/api/v1/im/message` 返回 HTTP 200，但消息没有实际送达。

### Share the target chat context

默认将 `ASTRBOT_CHAT_SESSION_ID` 留空。后端会自动复用 `ASTRBOT_TARGET_UMO` 作为 AstrBot Chat API 的 `session_id`，因此桌宠触摸事件和目标 QQ 私聊进入同一个上下文：用户触摸桌宠后，AI 在后续 QQ 对话中也知道这次触摸。

```dotenv
ASTRBOT_TARGET_UMO=platform_id:FriendMessage:session_id
ASTRBOT_CHAT_SESSION_ID=
```

如果明确希望桌宠对话与 QQ 私聊相互隔离，才设置一个独立值：

```dotenv
ASTRBOT_CHAT_SESSION_ID=touch_pet_signal
```

服务启动日志会显示当前使用“目标聊天同一上下文”还是“独立上下文”，但不会输出完整 UMO。

### Customize the pet

公共模板中的宠物不固定。你可以修改：

- `pet-config.js`：宠物名称、图片路径、替代文本和界面提示
- `assets/`：替换成自己的透明背景 PNG、WebP、SVG 或像素图
- `.env`：修改四种触摸操作实际发送给 AI 的文字
- `manifest.json`：修改 PWA 名称与主屏幕图标

建议保留四个手势键：

```text
tap
long_press
drag
double_tap
```

## Run

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8443
```

健康检查：

```text
http://YOUR_SERVER_IP:8443/api/health
```

网页：

```text
http://YOUR_SERVER_IP:8443/
```

只需向公网开放桌宠端口。AstrBot HTTP API 端口应尽量保持仅服务器内部可访问。

## iOS PWA

在 Safari 中打开网页，选择“分享 → 添加到主屏幕”。

HTTP 可以用于短期联调，但公网 PWA、Service Worker 和配对令牌传输应使用 HTTPS。长期部署请配置域名与证书。

## Android cross-app overlay

Android 原生版位于 [`android/`](android/)，支持：

- 使用 `TYPE_APPLICATION_OVERLAY` 显示在其他 App 上层
- 全屏拖动、边界限制与位置保存
- 单击、长按、拖拽、双击触摸信号
- 前台服务与常驻通知
- 通知栏停止服务
- 复用同一个 FastAPI `/api/touch` 后端

使用 Android Studio 打开 `android/`，等待 Gradle 同步后运行 `app`。首次启动：

1. 填写桌宠服务器 URL 与配对令牌。
2. 点击“保存并显示悬浮桌宠”。
3. 按系统提示允许“显示在其他应用上层”。
4. 返回应用，再点一次启动桌宠。

替换 Android 宠物素材：

```text
android/app/src/main/res/drawable/pet_placeholder.xml
```

也可以换成自己的 PNG/WebP，并同步修改 `OverlayPetService.kt` 中的资源名称。

Android 版为了兼容第一阶段 HTTP 联调，Manifest 暂时启用了 `usesCleartextTraffic="true"`。公开或长期部署应使用 HTTPS，并将它改为 `false`。

系统悬浮窗属于特殊权限，必须由用户主动授权。若计划上架应用商店，还需要遵守对应商店关于悬浮窗和前台服务的审核规则。

## iOS Live Activity and Dynamic Island

高版本 iOS 原生版位于 [`ios-live-activity/`](ios-live-activity/)，支持：

- ActivityKit 实时活动生命周期
- 锁屏实时活动
- 灵动岛紧凑、最小和展开布局
- 使用 App Intents 按钮发送轻戳、摸摸和连续触摸信号
- 与 Web、Android 版复用同一个 `/api/touch` 后端

需要 macOS、Xcode、Apple 开发签名与 XcodeGen。进入目录生成工程：

```bash
cd ios-live-activity
xcodegen generate
open AstrBotTouchPet.xcodeproj
```

灵动岛由 iOS 系统管理，不能像 Android 系统悬浮窗一样自由移动或覆盖任意 App。没有灵动岛的兼容设备仍可使用锁屏实时活动；普通桌宠交互继续使用 PWA 版。

详细签名、Bundle ID 与 App Group 配置见 [`ios-live-activity/README.md`](ios-live-activity/README.md)。

## AstrBot 4.22.3 Notes

### SSE text format

实机返回可能包含：

```json
{"type":"plain","data":"文本内容"}
```

本项目的 `extract_event_text()` 已兼容该格式。

### Docker persistence

- 固定明确的 AstrBot 镜像版本，不依赖会漂移的 `latest`
- 将代码、`.env` 和 `.venv` 放在持久化目录
- 容器重建后，原有服务进程需要重新启动
- 安装在容器系统层的临时软件包会在重建后消失
- 网页打不开时，依次检查进程监听、Docker 端口映射、安全组和防火墙

## Security

公开提交前，请确认仓库中不存在：

- `.env`
- API Key 或 Token
- 配对令牌
- 真实 QQ 号或用户 ID
- 完整 UMO
- 服务器公网 IP
- 日志、数据库和备份文件
- 私人角色图片或私人对话资料

建议提交前执行：

```bash
git status --short
git diff --cached
```

## Tests

```bash
python -m unittest discover -s tests -v
python -m py_compile server.py
```

## License

[MIT](LICENSE)
