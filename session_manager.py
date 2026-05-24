"""
Session 状态管理 — 轻量状态机
"""
import time

MODES = ("normal", "danger", "human", "faq", "smalltalk")
MAX_HISTORY = 8


class SessionManager:

    def __init__(self):
        self._s = {}
        self._last_cleanup = time.time()

    def _cleanup(self):
        now = time.time()
        if now - self._last_cleanup < 300:  # 每5分钟清理一次
            return
        self._last_cleanup = now
        expired = [sid for sid, s in self._s.items()
                   if now - s.get("last_active", 0) > 3600]
        for sid in expired:
            del self._s[sid]

    def get(self, sid: str) -> dict:
        self._cleanup()
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

    def enter_recovery(self, sid: str):
        """进入风险恢复确认状态"""
        self.get(sid)["recovering"] = True

    def exit_recovery(self, sid: str):
        """退出风险恢复状态"""
        s = self.get(sid)
        s["recovering"] = False

    def is_recovering(self, sid: str) -> bool:
        return self.get(sid).get("recovering", False)

    def confirm_leave_danger(self, sid: str):
        """用户确认安全，正式退出危险"""
        s = self.get(sid)
        s["mode"] = "normal"
        s["recovering"] = False

    def cancel_danger(self, sid: str):
        """取消危险模式"""
        s = self.get(sid)
        s["mode"] = "normal"
        s["recovering"] = False

    def _new(self) -> dict:
        return {
            "mode": "normal",
            "history": [],
            "last_topic": None,
            "last_active": time.time(),
            "recovering": False,
        }


sessions = SessionManager()
