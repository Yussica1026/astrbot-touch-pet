"""可配置触摸桌宠 PWA：静态页面 + 触摸信号 + AstrBot 主动消息。"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("astrbot-touch-pet")

SIGNALS = {
    "tap": os.getenv("SIGNAL_TAP", "用户戳了你一下"),
    "long_press": os.getenv("SIGNAL_LONG_PRESS", "用户正在抚摸你"),
    "drag": os.getenv("SIGNAL_DRAG", "用户拖动了你"),
    "double_tap": os.getenv("SIGNAL_DOUBLE_TAP", "用户连续戳了你两下"),
}


class TouchRequest(BaseModel):
    gesture: str
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")


class Settings:
    def __init__(self) -> None:
        self.astrbot_base_url = os.getenv("ASTRBOT_BASE_URL", "http://127.0.0.1:6185").rstrip("/")
        self.astrbot_api_key = os.getenv("ASTRBOT_API_KEY", "")
        self.target_umo = os.getenv("ASTRBOT_TARGET_UMO", "")
        # AstrBot OpenAPI 会把 username 作为 sender/user_id；如需关联记忆，请在 .env 中填写对应 ID。
        self.chat_username = os.getenv("ASTRBOT_CHAT_USERNAME", "touch_pet_user")
        # 默认复用目标聊天的完整 UMO，让触摸事件进入同一个上下文；显式填写时才创建独立上下文。
        self.configured_chat_session_id = os.getenv("ASTRBOT_CHAT_SESSION_ID", "").strip()
        # 新变量优先；旧变量仅用于兼容早期私人原型。
        self.pair_token = os.getenv("TOUCH_PET_PAIR_TOKEN", os.getenv("STONE_DOG_PAIR_TOKEN", ""))
        self.cooldown = max(1, int(os.getenv("COOLDOWN_SECONDS", "30")))
        self.hourly_limit = max(1, int(os.getenv("MAX_REQUESTS_PER_HOUR", "60")))
        self.timeout = max(10.0, float(os.getenv("ASTRBOT_TIMEOUT_SECONDS", "120")))
        self.context_db_path = os.getenv("ASTRBOT_CONTEXT_DB_PATH", "/AstrBot/data/data_v4.db")
        self.context_limit = max(1, min(int(os.getenv("ASTRBOT_CONTEXT_LIMIT", "10")), 50))

    @property
    def chat_session_id(self) -> str:
        return self.configured_chat_session_id or self.target_umo

    @property
    def shares_target_context(self) -> bool:
        return self.chat_session_id == self.target_umo

    def validate(self) -> None:
        missing = []
        if not self.astrbot_api_key:
            missing.append("ASTRBOT_API_KEY")
        if not self.pair_token:
            missing.append("TOUCH_PET_PAIR_TOKEN")
        if not self.target_umo:
            missing.append("ASTRBOT_TARGET_UMO")
        if missing:
            raise RuntimeError("缺少服务器私密配置：" + ", ".join(missing))


settings = Settings()
app = FastAPI(title="AstrBot Touch Pet", docs_url=None, redoc_url=None)
state_lock = asyncio.Lock()
last_delivered_at = 0.0
recent_requests: dict[str, float] = {}
hourly_requests: dict[str, deque[float]] = defaultdict(deque)


def astrbot_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.astrbot_api_key}", "Content-Type": "application/json"}


def extract_event_text(payload: Any) -> str:
    """提取 AstrBot 4.22 SSE 中的文本组件，同时兼容非流式 JSON。"""
    if not isinstance(payload, dict):
        return ""
    chain_type = payload.get("chain_type")
    if not chain_type and isinstance(payload.get("data"), dict):
        chain_type = payload["data"].get("chain_type")
    if chain_type and str(chain_type).lower() not in {"llm", "assistant", "final"}:
        return ""
    # AstrBot 4.22.3 实机返回的 plain 事件：{"type":"plain","data":"文本"}。
    if payload.get("type") == "plain" and isinstance(payload.get("data"), str):
        return payload["data"]
    paths = (
        ("data", "content", "data", "text"),
        ("data", "content", "text"),
        ("data", "text"),
        ("content", "data", "text"),
        ("content", "text"),
        ("completion_text",),
        ("response",),
        ("text",),
    )
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if isinstance(value, str) and value.strip():
            return value
    return ""


def merge_text(current: str, chunk: str) -> str:
    """兼容增量片段与累计片段，避免重复拼接。"""
    if not chunk:
        return current
    if not current or chunk.startswith(current):
        return chunk
    if current.endswith(chunk):
        return current
    return current + chunk


def _conversation_text(value: Any) -> list[str]:
    """从 AstrBot conversations 字段中递归提取用户与助手的纯文本。"""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return [value.strip()] if value.strip() else []
        return _conversation_text(decoded)
    if isinstance(value, list):
        rows: list[str] = []
        for item in value:
            rows.extend(_conversation_text(item))
        return rows
    if not isinstance(value, dict):
        return []
    role = str(value.get("role") or value.get("sender") or "").strip()
    content = value.get("content", value.get("message", value.get("text")))
    if isinstance(content, str) and content.strip():
        label = "用户" if role in {"user", "human"} else "AI" if role in {"assistant", "ai"} else role
        return [f"{label}：{content.strip()}" if label else content.strip()]
    rows: list[str] = []
    for key, item in value.items():
        if key not in {"id", "session_id", "created_at", "updated_at"}:
            rows.extend(_conversation_text(item))
    return rows


def fetch_qq_context() -> str:
    """从 AstrBot data_v4.db 的 conversations 表读取最近聊天；失败时安全降级为空。"""
    path = Path(settings.context_db_path)
    if not path.is_file():
        return ""
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        columns = [row[1] for row in connection.execute("PRAGMA table_info(conversations)")]
        if not columns:
            return ""
        order = next((name for name in ("updated_at", "created_at", "id") if name in columns), columns[0])
        rows = connection.execute(f'SELECT * FROM conversations ORDER BY "{order}" DESC LIMIT 20').fetchall()
        extracted: list[str] = []
        for row in rows:
            for key in ("history", "messages", "content", "conversation"):
                if key in columns and row[key]:
                    extracted.extend(_conversation_text(row[key]))
                    break
        return "\n".join(extracted[-settings.context_limit :])
    except (OSError, sqlite3.Error, ValueError, TypeError):
        logger.warning("读取 AstrBot conversations 上下文失败", exc_info=True)
        return ""
    finally:
        if "connection" in locals():
            connection.close()


async def generate_reply(client: httpx.AsyncClient, signal: str) -> str:
    context = fetch_qq_context()
    message = f"<recent_qq_context>\n{context}\n</recent_qq_context>\n\n{signal}" if context else signal
    body = {
        "username": settings.chat_username,
        "session_id": settings.chat_session_id,
        # 只传递触摸事实，不写台词、不指定语气，回复完全交给目标 AI。
        "message": message,
        "enable_streaming": False,
    }
    reply = ""
    async with client.stream(
        "POST", f"{settings.astrbot_base_url}/api/v1/chat", headers=astrbot_headers(), json=body
    ) as response:
        if response.status_code >= 400:
            detail = (await response.aread()).decode("utf-8", "replace")[:500]
            raise RuntimeError(f"AstrBot chat 返回 {response.status_code}: {detail}")
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = json.loads((await response.aread()).decode("utf-8"))
            reply = extract_event_text(payload)
        else:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    chunk = extract_event_text(json.loads(raw))
                except json.JSONDecodeError:
                    continue
                reply = merge_text(reply, chunk)
    reply = reply.strip()
    if not reply:
        raise RuntimeError("AstrBot chat 没有返回可发送的文本")
    return reply[:1500]


async def send_qq_message(client: httpx.AsyncClient, reply: str) -> None:
    response = await client.post(
        f"{settings.astrbot_base_url}/api/v1/im/message",
        headers=astrbot_headers(),
        json={"umo": settings.target_umo, "message": reply},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"AstrBot IM 返回 {response.status_code}: {response.text[:500]}")


async def notify_qq(client: httpx.AsyncClient, text: str) -> None:
    """直接向目标 QQ 转发用户原始输入，不调用模型、不消耗 token。"""
    await send_qq_message(client, text[:2000])


def verify_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少配对令牌")
    token = authorization[7:].strip()
    if not hmac.compare_digest(token, settings.pair_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="配对令牌不正确")
    return "paired-device"


@app.on_event("startup")
async def startup() -> None:
    settings.validate()
    context_mode = "目标聊天同一上下文" if settings.shares_target_context else "独立上下文"
    logger.info("触摸桌宠服务启动；AstrBot=%s；目标 UMO 已配置；会话模式=%s", settings.astrbot_base_url, context_mode)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "astrbot-touch-pet", "astrbot_version_expected": "4.22.3"}


@app.post("/api/touch")
async def touch(body: TouchRequest, request: Request, authorization: str | None = Header(default=None)) -> JSONResponse:
    global last_delivered_at
    device = verify_token(authorization)
    if body.gesture not in SIGNALS:
        raise HTTPException(status_code=422, detail="不支持的触摸类型")

    now = time.monotonic()
    async with state_lock:
        expired = [key for key, when in recent_requests.items() if now - when > 3600]
        for key in expired:
            recent_requests.pop(key, None)
        if body.request_id in recent_requests:
            return JSONResponse({"ok": True, "status": "duplicate", "cooldown_seconds": settings.cooldown})

        window = hourly_requests[device]
        while window and now - window[0] >= 3600:
            window.popleft()
        if len(window) >= settings.hourly_limit:
            raise HTTPException(status_code=429, detail="每小时触摸次数已达到上限", headers={"Retry-After": "3600"})
        retry_after = settings.cooldown - (now - last_delivered_at)
        if retry_after > 0:
            return JSONResponse(
                {"ok": False, "detail": "信号正在冷却", "retry_after": int(retry_after) + 1},
                status_code=429,
            )
        # 在网络调用前占位，防止并发请求同时通过。
        last_delivered_at = now
        recent_requests[body.request_id] = now
        window.append(now)

    signal = SIGNALS[body.gesture]
    try:
        async with httpx.AsyncClient(timeout=settings.timeout) as client:
            await notify_qq(client, signal)
            reply = await generate_reply(client, signal)
            await send_qq_message(client, reply)
    except Exception as exc:
        async with state_lock:
            if last_delivered_at == now:
                last_delivered_at = 0.0
            recent_requests.pop(body.request_id, None)
            try:
                hourly_requests[device].remove(now)
            except ValueError:
                pass
        logger.exception("触摸信号投递失败：gesture=%s", body.gesture)
        raise HTTPException(status_code=502, detail=f"AstrBot 投递失败：{exc}") from exc

    logger.info("触摸信号已投递：gesture=%s request=%s", body.gesture, body.request_id[:12])
    return JSONResponse({"ok": True, "status": "delivered", "cooldown_seconds": settings.cooldown})


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request, authorization: str | None = Header(default=None)) -> JSONResponse:
    global last_delivered_at
    device = verify_token(authorization)
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")
    now = time.monotonic()
    async with state_lock:
        if body.request_id in recent_requests:
            return JSONResponse({"ok": True, "status": "duplicate", "cooldown_seconds": settings.cooldown})
        window = hourly_requests[device]
        while window and now - window[0] >= 3600:
            window.popleft()
        if len(window) >= settings.hourly_limit:
            raise HTTPException(status_code=429, detail="每小时消息次数已达到上限", headers={"Retry-After": "3600"})
        retry_after = settings.cooldown - (now - last_delivered_at)
        if retry_after > 0:
            return JSONResponse({"ok": False, "detail": "消息正在冷却", "retry_after": int(retry_after) + 1}, status_code=429)
        last_delivered_at = now
        recent_requests[body.request_id] = now
        window.append(now)
    try:
        async with httpx.AsyncClient(timeout=settings.timeout) as client:
            await notify_qq(client, message)
            reply = await generate_reply(client, message)
            await send_qq_message(client, reply)
    except Exception as exc:
        async with state_lock:
            if last_delivered_at == now:
                last_delivered_at = 0.0
            recent_requests.pop(body.request_id, None)
            try:
                hourly_requests[device].remove(now)
            except ValueError:
                pass
        logger.exception("文字消息投递失败")
        raise HTTPException(status_code=502, detail=f"AstrBot 投递失败：{exc}") from exc
    logger.info("文字消息已投递：request=%s", body.request_id[:12])
    return JSONResponse({"ok": True, "status": "delivered", "cooldown_seconds": settings.cooldown})


# 必须最后挂载，否则静态路由会遮住 /api。
app.mount("/", StaticFiles(directory=ROOT, html=True), name="pwa")
