"""
Session 状态管理 — 纯规则状态机，AI 不能决定 mode
"""
import time
from typing import Optional

VALID_MODES = ("normal", "danger", "faq", "human", "smalltalk")


class SessionManager:
    """管理每个用户会话的状态"""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get(self, session_id: str) -> dict:
        """获取或创建 session"""
        if session_id not in self._sessions:
            self._sessions[session_id] = self._create()
        s = self._sessions[session_id]
        s["last_active"] = time.time()
        return s

    def set_mode(self, session_id: str, mode: str):
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}, must be one of {VALID_MODES}")
        s = self.get(session_id)
        s["mode"] = mode
        s["last_active"] = time.time()

    def get_mode(self, session_id: str) -> str:
        return self.get(session_id)["mode"]

    def reset(self, session_id: str):
        """新对话时重置 session"""
        self._sessions[session_id] = self._create()

    def confirm_danger(self, session_id: str):
        s = self.get(session_id)
        s["danger_confirmed"] = True
        s["mode"] = "danger"

    def cancel_danger(self, session_id: str):
        """退出 danger 模式"""
        s = self.get(session_id)
        s["mode"] = "normal"
        s["danger_confirmed"] = False
        s["last_topic"] = ""

    def set_topic(self, session_id: str, topic: str):
        self.get(session_id)["last_topic"] = topic

    def get_topic(self, session_id: str) -> str:
        return self.get(session_id).get("last_topic", "")

    def set_last_faq_answer(self, session_id: str, answer: str):
        self.get(session_id)["last_faq_answer"] = answer

    def get_last_faq_answer(self, session_id: str) -> str:
        return self.get(session_id).get("last_faq_answer", "")

    def cleanup(self, max_age_seconds: int = 3600):
        """清理过期 session"""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.get("last_active", 0) > max_age_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

    @staticmethod
    def _create() -> dict:
        return {
            "mode": "normal",
            "danger_confirmed": False,
            "last_topic": "",
            "last_faq_answer": "",
            "last_active": time.time(),
        }


# 全局单例
session_manager = SessionManager()
