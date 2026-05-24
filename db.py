"""
持久化存储 — Supabase PostgreSQL
部署不丢数据
"""
import json, urllib.request, urllib.error
from datetime import datetime, timedelta

URL = "https://xvdyjppowidwquupawje.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2ZHlqcHBvd2lkd3F1dXBhd2plIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTYyNzEyOSwiZXhwIjoyMDk1MjAzMTI5fQ.3eR8ae_rmmFreWR1k8DZp7nrZ0cb_81ScefU8s4XQ50"
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def _post(table: str, data: dict):
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}",
            data=json.dumps(data).encode(), headers=H, method="POST")
        req.add_header("Prefer", "return=representation")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[DB] {table} error: {e}")


def _get(table: str, select: str = "*", where: str = "", order: str = "", limit: int = 50) -> list[dict]:
    try:
        url = f"{URL}/rest/v1/{table}?select={select}"
        if where: url += f"&{where}"
        if order: url += f"&order={order}"
        if limit: url += f"&limit={limit}"
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()) or []
    except Exception:
        return []


def _patch(table: str, where: str, data: dict):
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}?{where}",
            data=json.dumps(data).encode(), headers=H, method="PATCH")
        req.add_header("Prefer", "return=minimal")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[DB] {table} error: {e}")


def _delete(table: str, where: str):
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}?{where}", headers=H, method="DELETE")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[DB] {table} error: {e}")


# ═══ 工单 ═══

def add_ticket(ticket_id: str, question: str, risk_level: str, ip: str = "", user_id: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _post("tickets", {"id": ticket_id, "created_at": now, "user_question": question,
        "risk_level": risk_level, "user_ip": ip, "user_id": user_id})
    return {"工单ID": ticket_id, "时间": now, "用户问题": question,
            "风险等级": risk_level, "分类": "紧急事件", "状态": "处理中",
            "处理人": "调度中心A组", "用户IP": ip, "用户标识": user_id}


def get_tickets(limit: int = 20):
    return _get("tickets", order="created_at.desc", limit=limit)


def get_user_tickets(user_id: str):
    return _get("tickets", where=f"user_id=eq.{user_id}", order="created_at.desc", limit=50)


def resolve_ticket(ticket_id: str):
    _patch("tickets", f"id=eq.{ticket_id}", {"status": "已解决"})


def archive_resolved():
    _delete("tickets", "status=eq.已解决")


def ticket_count():
    return len(_get("tickets", select="id", limit=100000))


# ═══ 对话记录 ═══

def add_chat(question: str, reply: str, mode: str = "", source: str = ""):
    _post("chat_logs", {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_question": question[:200], "ai_reply": reply[:200], "mode": mode, "source": source})


def get_chat_logs(limit: int = 50):
    return _get("chat_logs", order="created_at.desc", limit=limit)


# ═══ 安全日志 ═══

def add_emergency_log(question: str, risk_level: str, ip: str = "", ticket_id: str = ""):
    _post("emergency_logs", {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_level": risk_level, "user_ip": ip, "ticket_id": ticket_id, "user_question": question[:200]})


def get_emergency_logs(limit: int = 20):
    rows = _get("emergency_logs", order="created_at.desc", limit=limit)
    return [f"[{r['created_at']}] [{r['risk_level']}] TICKET={r.get('ticket_id','')} Q={r.get('user_question','')}" for r in rows]


def emergency_log_count():
    return len(_get("emergency_logs", select="id", limit=100000))


def get_risk_trends(days: int = 7):
    today = datetime.now()
    trends = {(today - timedelta(days=i)).strftime("%Y-%m-%d"): {"high": 0, "medium": 0, "total": 0}
              for i in range(days - 1, -1, -1)}
    for r in get_tickets(100000):
        d = (r.get("created_at", "") or "")[:10]
        if d in trends:
            trends[d]["total"] += 1
            if r.get("risk_level", "") in ("高危", "紧急"): trends[d]["high"] += 1
            else: trends[d]["medium"] += 1
    return list(trends.items())
