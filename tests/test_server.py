import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import httpx

import server


class AstrBotBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_sse_then_im_delivery(self):
        sent = {}

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if request.url.path == "/api/v1/chat":
                self.assertEqual(body["username"], "test_user")
                self.assertEqual(body["session_id"], "test-platform:FriendMessage:test-session")
                self.assertEqual(body["message"], "用户戳了你一下")
                stream = (
                    'data: {"type":"message","data":{"content":{"type":"text","data":{"text":"收到，"}}}}\n\n'
                    'data: {"type":"message","data":{"content":{"type":"text","data":{"text":"我感觉到了。"}}}}\n\n'
                    "data: [DONE]\n\n"
                )
                return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=stream)
            if request.url.path == "/api/v1/im/message":
                sent.update(body)
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://astrbot") as client:
            old_base = server.settings.astrbot_base_url
            old_username = server.settings.chat_username
            old_umo = server.settings.target_umo
            old_session_id = server.settings.configured_chat_session_id
            server.settings.astrbot_base_url = "http://astrbot"
            server.settings.chat_username = "test_user"
            server.settings.target_umo = "test-platform:FriendMessage:test-session"
            server.settings.configured_chat_session_id = ""
            try:
                reply = await server.generate_reply(client, "用户戳了你一下")
                await server.send_qq_message(client, reply)
            finally:
                server.settings.astrbot_base_url = old_base
                server.settings.chat_username = old_username
                server.settings.target_umo = old_umo
                server.settings.configured_chat_session_id = old_session_id

        self.assertEqual(reply, "收到，我感觉到了。")
        self.assertEqual(sent["umo"], "test-platform:FriendMessage:test-session")
        self.assertEqual(sent["message"], reply)

    def test_extract_astrbot_plain_event(self):
        payload = {"type": "plain", "data": "实机返回文本"}
        self.assertEqual(server.extract_event_text(payload), "实机返回文本")

    def test_tool_chain_event_is_not_rendered_as_reply(self):
        payload = {"chain_type": "tool", "data": {"text": '{"name":"fetch"}'}}
        self.assertEqual(server.extract_event_text(payload), "")

    def test_context_comes_from_conversations_table(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data_v4.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE conversations (id TEXT, history TEXT, updated_at TEXT)")
            history = json.dumps([
                {"role": "user", "content": "第一条"},
                {"role": "assistant", "content": "第二条"},
            ], ensure_ascii=False)
            connection.execute("INSERT INTO conversations VALUES ('qq', ?, '2026-08-07')", (history,))
            connection.commit()
            connection.close()
            old_path = server.settings.context_db_path
            server.settings.context_db_path = str(path)
            try:
                context = server.fetch_qq_context()
            finally:
                server.settings.context_db_path = old_path
        self.assertEqual(context, "用户：第一条\nAI：第二条")

    def test_signal_whitelist(self):
        self.assertEqual(set(server.SIGNALS), {"tap", "long_press", "drag", "double_tap"})

    def test_explicit_session_keeps_context_isolated(self):
        old_umo = server.settings.target_umo
        old_session_id = server.settings.configured_chat_session_id
        server.settings.target_umo = "platform:FriendMessage:session"
        server.settings.configured_chat_session_id = "touch_pet_signal"
        try:
            self.assertEqual(server.settings.chat_session_id, "touch_pet_signal")
            self.assertFalse(server.settings.shares_target_context)
        finally:
            server.settings.target_umo = old_umo
            server.settings.configured_chat_session_id = old_session_id


if __name__ == "__main__":
    unittest.main()
