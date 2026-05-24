"""
SQLite 持久化存储 — 替代 CSV 文件
工单、对话记录、安全日志
"""
import sqlite3, os, threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hengyang.db")
_local = threading.local()


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            user_question TEXT,
            risk_level TEXT,
            category TEXT DEFAULT '紧急事件',
            status TEXT DEFAULT '处理中',
            handler TEXT DEFAULT '调度中心A组',
            user_ip TEXT DEFAULT '',
            user_id TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_question TEXT,
            ai_reply TEXT,
            mode TEXT,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS emergency_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            risk_level TEXT,
            user_ip TEXT,
            ticket_id TEXT,
            user_question TEXT
        );
    """)
    c.commit()


# ═══════════════════════════════════════════
# 工单
# ═══════════════════════════════════════════

def add_ticket(ticket_id: str, question: str, risk_level: str,
               ip: str = "", user_id: str = "") -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _conn().execute(
        "INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?,?,?)",
        (ticket_id, now, question, risk_level, "紧急事件", "处理中", "调度中心A组", ip, user_id)
    )
    _conn().commit()
    return {
        "工单ID": ticket_id, "时间": now, "用户问题": question,
        "风险等级": risk_level, "分类": "紧急事件", "状态": "处理中",
        "处理人": "调度中心A组", "用户IP": ip, "用户标识": user_id,
    }


def get_tickets(limit: int = 20) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_user_tickets(user_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM tickets WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_ticket(ticket_id: str):
    _conn().execute("UPDATE tickets SET status='已解决' WHERE id=?", (ticket_id,))
    _conn().commit()


def archive_resolved():
    c = _conn()
    c.execute("DELETE FROM tickets WHERE status='已解决'")
    c.commit()


def ticket_count() -> int:
    return _conn().execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


# ═══════════════════════════════════════════
# 对话记录
# ═══════════════════════════════════════════

def add_chat(question: str, reply: str, mode: str = "", source: str = ""):
    _conn().execute(
        "INSERT INTO chat_logs VALUES (NULL,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), question[:200], reply[:200], mode, source)
    )
    _conn().commit()


def get_chat_logs(limit: int = 50) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
# 安全日志
# ═══════════════════════════════════════════

def add_emergency_log(question: str, risk_level: str, ip: str = "", ticket_id: str = ""):
    _conn().execute(
        "INSERT INTO emergency_logs VALUES (NULL,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), risk_level, ip, ticket_id, question[:200])
    )
    _conn().commit()


def get_emergency_logs(limit: int = 20) -> list[str]:
    rows = _conn().execute(
        "SELECT * FROM emergency_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [f"[{r['created_at']}] [{r['risk_level']}] IP={r['user_ip']} TICKET={r['ticket_id']} Q={r['user_question']}" for r in rows]


def emergency_log_count() -> int:
    return _conn().execute("SELECT COUNT(*) FROM emergency_logs").fetchone()[0]


# ═══════════════════════════════════════════
# 风险趋势
# ═══════════════════════════════════════════

def get_risk_trends(days: int = 7) -> list:
    from datetime import timedelta
    today = datetime.now()
    trends = {}
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        trends[d] = {"high": 0, "medium": 0, "total": 0}
    rows = _conn().execute(
        "SELECT created_at, risk_level FROM tickets ORDER BY created_at"
    ).fetchall()
    for r in rows:
        d = r["created_at"][:10]
        if d in trends:
            trends[d]["total"] += 1
            if r["risk_level"] in ("高危", "紧急"):
                trends[d]["high"] += 1
            else:
                trends[d]["medium"] += 1
    return list(trends.items())


# 启动时初始化
init()
