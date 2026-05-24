"""
持久化存储 — Supabase (PostgreSQL) 优先，SQLite 兜底
部署不丢数据：Supabase 免费 500MB，Render 重启/部署数据保留

设置环境变量：
  SUPABASE_URL=https://xxxxx.supabase.co
  SUPABASE_KEY=eyJ... (service_role key)
"""
import os, json
from datetime import datetime, timedelta
from config import SUPABASE_URL, SUPABASE_KEY, ENABLE_SUPABASE

# ═══════════════════════════════════════════
# Supabase 客户端
# ═══════════════════════════════════════════

class _SupabaseDB:
    """Supabase REST API 封装"""

    def __init__(self):
        self.url = SUPABASE_URL.rstrip("/")
        self.key = SUPABASE_KEY
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._init_tables()

    def _init_tables(self):
        """通过 REST 创建表（首次自动建表）"""
        import urllib.request
        ddl = """
        create table if not exists tickets (
            id text primary key,
            created_at text not null,
            user_question text,
            risk_level text,
            category text default '紧急事件',
            status text default '处理中',
            handler text default '调度中心A组',
            user_ip text default '',
            user_id text default ''
        );
        create table if not exists chat_logs (
            id serial primary key,
            created_at text not null,
            user_question text,
            ai_reply text,
            mode text,
            source text
        );
        create table if not exists emergency_logs (
            id serial primary key,
            created_at text not null,
            risk_level text,
            user_ip text,
            ticket_id text,
            user_question text
        );
        """
        # Supabase 需要通过 SQL Editor 或管理 API 执行 DDL
        # REST API 不支持直接执行 DDL，这里记录日志
        pass

    def _post(self, table: str, data: dict) -> dict | None:
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(
                f"{self.url}/rest/v1/{table}",
                data=json.dumps(data).encode(),
                headers=self._headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())[0] if resp.status == 201 else None
        except Exception:
            return None

    def _get(self, table: str, query: str = "", order: str = "", limit: int = 50) -> list[dict]:
        import urllib.request, urllib.error
        try:
            url = f"{self.url}/rest/v1/{table}?select=*"
            if query:
                url += f"&{query}"
            if order:
                url += f"&order={order}"
            if limit:
                url += f"&limit={limit}"
            req = urllib.request.Request(url, headers=self._headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read()) or []
        except Exception:
            return []

    def _patch(self, table: str, query: str, data: dict) -> bool:
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(
                f"{self.url}/rest/v1/{table}?{query}",
                data=json.dumps(data).encode(),
                headers={**self._headers, "Prefer": "return=minimal"},
                method="PATCH",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def _delete(self, table: str, query: str) -> bool:
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(
                f"{self.url}/rest/v1/{table}?{query}",
                headers=self._headers,
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False


# ═══════════════════════════════════════════
# SQLite 兜底
# ═══════════════════════════════════════════

class _SQLiteDB:
    def __init__(self):
        import sqlite3, threading
        self._local = threading.local()
        self._path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hengyang.db")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _conn(self):
        import sqlite3
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init(self):
        c = self._conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, created_at TEXT, user_question TEXT, risk_level TEXT,
                category TEXT, status TEXT, handler TEXT, user_ip TEXT, user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT,
                user_question TEXT, ai_reply TEXT, mode TEXT, source TEXT
            );
            CREATE TABLE IF NOT EXISTS emergency_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT,
                risk_level TEXT, user_ip TEXT, ticket_id TEXT, user_question TEXT
            );
        """)
        c.commit()


# ═══════════════════════════════════════════
# 统一接口（Supabase 优先）
# ═══════════════════════════════════════════

if ENABLE_SUPABASE:
    _db = _SupabaseDB()
    _STORE = "supabase"
else:
    _db = _SQLiteDB()
    _db._init()
    _STORE = "sqlite"

print(f"[DB] 存储引擎: {_STORE}")


def add_ticket(ticket_id: str, question: str, risk_level: str,
               ip: str = "", user_id: str = "") -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "id": ticket_id, "created_at": now, "user_question": question,
        "risk_level": risk_level, "category": "紧急事件", "status": "处理中",
        "handler": "调度中心A组", "user_ip": ip, "user_id": user_id,
    }
    if _STORE == "supabase":
        _db._post("tickets", data)
    else:
        c = _db._conn()
        c.execute("INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?,?,?)",
                  (ticket_id, now, question, risk_level, "紧急事件", "处理中", "调度中心A组", ip, user_id))
        c.commit()
    return {"工单ID": ticket_id, "时间": now, "用户问题": question,
            "风险等级": risk_level, "分类": "紧急事件", "状态": "处理中",
            "处理人": "调度中心A组", "用户IP": ip, "用户标识": user_id}


def get_tickets(limit: int = 20) -> list[dict]:
    if _STORE == "supabase":
        return _db._get("tickets", order="created_at.desc", limit=limit)
    rows = _db._conn().execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_user_tickets(user_id: str) -> list[dict]:
    if _STORE == "supabase":
        return _db._get("tickets", query=f"user_id=eq.{user_id}", order="created_at.desc", limit=50)
    rows = _db._conn().execute("SELECT * FROM tickets WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def resolve_ticket(ticket_id: str):
    if _STORE == "supabase":
        _db._patch("tickets", f"id=eq.{ticket_id}", {"status": "已解决"})
    else:
        c = _db._conn()
        c.execute("UPDATE tickets SET status='已解决' WHERE id=?", (ticket_id,))
        c.commit()


def archive_resolved():
    if _STORE == "supabase":
        _db._delete("tickets", "status=eq.已解决")
    else:
        c = _db._conn()
        c.execute("DELETE FROM tickets WHERE status='已解决'")
        c.commit()


def ticket_count() -> int:
    if _STORE == "supabase":
        rows = _db._get("tickets", query="select=id", limit=10000)
        return len(rows)
    return _db._conn().execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


def add_chat(question: str, reply: str, mode: str = "", source: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {"created_at": now, "user_question": question[:200],
            "ai_reply": reply[:200], "mode": mode, "source": source}
    if _STORE == "supabase":
        _db._post("chat_logs", data)
    else:
        c = _db._conn()
        c.execute("INSERT INTO chat_logs VALUES (NULL,?,?,?,?,?)",
                  (now, question[:200], reply[:200], mode, source))
        c.commit()


def get_chat_logs(limit: int = 50) -> list[dict]:
    if _STORE == "supabase":
        return _db._get("chat_logs", order="created_at.desc", limit=limit)
    rows = _db._conn().execute("SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def add_emergency_log(question: str, risk_level: str, ip: str = "", ticket_id: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {"created_at": now, "risk_level": risk_level, "user_ip": ip,
            "ticket_id": ticket_id, "user_question": question[:200]}
    if _STORE == "supabase":
        _db._post("emergency_logs", data)
    else:
        c = _db._conn()
        c.execute("INSERT INTO emergency_logs VALUES (NULL,?,?,?,?,?)",
                  (now, risk_level, ip, ticket_id, question[:200]))
        c.commit()


def get_emergency_logs(limit: int = 20) -> list[str]:
    if _STORE == "supabase":
        rows = _db._get("emergency_logs", order="created_at.desc", limit=limit)
        return [f"[{r['created_at']}] [{r['risk_level']}] IP={r.get('user_ip','')} TICKET={r.get('ticket_id','')} Q={r.get('user_question','')}" for r in rows]
    rows = _db._conn().execute("SELECT * FROM emergency_logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [f"[{r['created_at']}] [{r['risk_level']}] IP={r['user_ip']} TICKET={r['ticket_id']} Q={r['user_question']}" for r in rows]


def emergency_log_count() -> int:
    if _STORE == "supabase":
        rows = _db._get("emergency_logs", query="select=id", limit=10000)
        return len(rows)
    return _db._conn().execute("SELECT COUNT(*) FROM emergency_logs").fetchone()[0]


def get_risk_trends(days: int = 7) -> list:
    today = datetime.now()
    trends = {}
    for i in range(days - 1, -1, -1):
        trends[(today - timedelta(days=i)).strftime("%Y-%m-%d")] = {"high": 0, "medium": 0, "total": 0}

    tickets = get_tickets(10000)
    for r in tickets:
        d = (r.get("created_at", "") or "")[:10]
        if d in trends:
            trends[d]["total"] += 1
            if r.get("risk_level", "") in ("高危", "紧急"):
                trends[d]["high"] += 1
            else:
                trends[d]["medium"] += 1
    return list(trends.items())
