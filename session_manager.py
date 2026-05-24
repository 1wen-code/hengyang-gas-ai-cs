"""
Session 状态管理 — 轻量状态机
"""
import time

MODES = ("normal", "danger", "human", "faq", "smalltalk")
MAX_HISTORY = 8


class SessionManager:

    def __init__(self):
        self._s = {}

    def get(self, sid: str) -> dict:
        if sid not in self._s:
            self._s[sid] = self._new()
        self._s[sid]["last_active"] = time.time()
        return self._s[sid]

    def reset(self, sid: str):
        self._s[sid] = self._new()

    def set_mode(self, sid: str, mode: str):
        if mode not in MODES:
            return
        self.get(sid)["mode"] = mode

    def get_mode(self, sid: str) -> str:
        return self.get(sid)["mode"]

    def add_history(self, sid: str, role: str, content: str):
        s = self.get(sid)
        s["history"].append({"role": role, "content": content})
        if len(s["history"]) > MAX_HISTORY * 2:
            s["history"] = s["history"][-MAX_HISTORY * 2:]

    def get_history(self, sid: str) -> list:
        return self.get(sid)["history"]

    def set_topic(self, sid: str, topic: str):
        self.get(sid)["last_topic"] = topic

    def get_topic(self, sid: str) -> str | None:
        return self.get(sid)["last_topic"]

    def _new(self) -> dict:
        return {
            "mode": "normal",
            "history": [],
            "last_topic": None,
            "last_active": time.time(),
        }


sessions = SessionManager()
