"""
持久化存储 — Supabase PostgreSQL
部署不丢数据
"""
import json, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta

URL = "https://xvdyjppowidwquupawje.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2ZHlqcHBvd2lkd3F1dXBhd2plIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTYyNzEyOSwiZXhwIjoyMDk1MjAzMTI5fQ.3eR8ae_rmmFreWR1k8DZp7nrZ0cb_81ScefU8s4XQ50"
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def _enc(where: str) -> str:
    """PostgREST 的 where 子句要百分号编码。

    原先中文直接拼进 URL（如 status=eq.已解决），urllib 发送前会抛
    UnicodeEncodeError，被 except 吞掉 —— 于是"归档工单"永远删不掉却报成功。
    """
    return urllib.parse.quote(where, safe="=&")


def _post(table: str, data: dict) -> bool:
    """返回是否真的写成功 —— 调用方必须据此决定要不要告诉用户"""
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}",
            data=json.dumps(data).encode(), headers=H, method="POST")
        req.add_header("Prefer", "return=representation")
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"[DB] {table} error: {e}")
        return False


def _get(table: str, select: str = "*", where: str = "", order: str = "", limit: int = 50) -> list[dict]:
    try:
        url = f"{URL}/rest/v1/{table}?select={select}"
        if where: url += f"&{_enc(where)}"
        if order: url += f"&order={order}"
        if limit: url += f"&limit={limit}"
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()) or []
    except Exception:
        return []


def _patch(table: str, where: str, data: dict) -> bool:
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}?{_enc(where)}",
            data=json.dumps(data).encode(), headers=H, method="PATCH")
        req.add_header("Prefer", "return=minimal")
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"[DB] {table} error: {e}")
        return False


def _delete(table: str, where: str) -> bool:
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/{table}?{_enc(where)}",
            headers=H, method="DELETE")
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"[DB] {table} error: {e}")
        return False


# ═══ 工单 ═══

def _map_ticket(r: dict) -> dict:
    """Supabase英文字段 → 模板中文字段"""
    return {
        "工单ID": r.get("id", ""),
        "时间": r.get("created_at", ""),
        "用户问题": r.get("user_question", ""),
        "风险等级": r.get("risk_level", ""),
        "分类": r.get("category") or "紧急事件",
        "状态": r.get("status") or "处理中",
        "处理人": r.get("handler") or "调度中心A组",
        "用户IP": r.get("user_ip", ""),
        "用户标识": r.get("user_id", ""),
    }


def add_ticket(ticket_id: str, question: str, risk_level: str, ip: str = "", user_id: str = ""):
    """写入成功才返回工单对象；失败返回 None。

    原先无论写没写进去都把入参拼成工单返回，界面照样显示
    "已生成工单 EM-xxx"，而库里根本没有这条 —— 抢险工单不能这么假报。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {"id": ticket_id, "created_at": now, "user_question": question,
           "risk_level": risk_level, "category": "紧急事件", "status": "处理中",
           "user_ip": ip, "user_id": user_id}
    if not _post("tickets", row):
        return None
    return _map_ticket(row)


def get_tickets(limit: int = 20):
    return [_map_ticket(r) for r in _get("tickets", order="created_at.desc", limit=limit)]


def get_user_tickets(user_id: str):
    return [_map_ticket(r) for r in _get("tickets", where=f"user_id=eq.{user_id}", order="created_at.desc", limit=50)]


def resolve_ticket(ticket_id: str) -> bool:
    return _patch("tickets", f"id=eq.{ticket_id}", {"status": "已解决"})


def archive_resolved() -> bool:
    return _delete("tickets", "status=eq.已解决")


def ticket_count():
    return len(_get("tickets", select="id", limit=100000))


# ═══ 对话记录 ═══

def add_chat(question: str, reply: str, mode: str = "", source: str = ""):
    _post("chat_logs", {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_question": question[:200], "ai_reply": reply[:200], "mode": mode, "source": source})


def get_chat_logs(limit: int = 50):
    rows = _get("chat_logs", order="created_at.desc", limit=limit)
    return [{"用户问题": r.get("user_question", ""), "AI回答": r.get("ai_reply", ""),
             "时间": r.get("created_at", ""), "模式": r.get("mode", ""),
             "风险等级": r.get("risk_level", "普通")} for r in rows]


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
        d = (r.get("时间", "") or "")[:10]
        if d in trends:
            trends[d]["total"] += 1
            if r.get("风险等级", "") in ("高危", "紧急"): trends[d]["high"] += 1
            else: trends[d]["medium"] += 1
    return list(trends.items())
