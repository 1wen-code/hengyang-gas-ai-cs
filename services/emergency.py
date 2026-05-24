"""
衡阳市天然气AI客服 — 三级风险判断 + 工单生成
"""
import re, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 安全词 ──────────────────────────────────
SAFE_CONTEXTS = [
    "打不着", "打不燃", "点不着", "打不着火", "打不燃火",
    "没热水", "不出热水", "热水器.*不",
    "火焰.*小", "火.*小", "火苗.*小",
    "电池", "没电", "欠费", "充值",
    "怎么.*修", "排查",
    "不着火", "点不燃", "不打火",
    "火盖.*堵", "火孔.*堵",
]

LEVEL1_KEYWORDS = [
    "没热水", "打不着火", "火焰小", "红火", "黄火",
    "电池没电", "电池更换", "换电池", "欠费停气",
    "IC卡充值", "余额不足", "充值不到账",
]

LEVEL2_KEYWORDS = [
    "闻到煤气味", "闻到燃气味", "有煤气味", "有燃气味",
    "刺鼻气味", "异味", "臭味", "像漏气",
    "疑似漏气", "怀疑漏气", "可能漏气",
    "轻微泄漏", "一点点泄漏",
    "报警器", "报警器响了", "燃气报警器",
    "燃气表一直走", "阀门漏气",
    "头晕", "恶心", "不舒服", "胸闷",
    "燃气味", "煤气味",
    "燃气泄漏", "漏气", "天然气泄漏",
]

LEVEL3_KEYWORDS = [
    "爆炸", "爆燃", "炸了", "着火", "起火", "火灾", "明火",
    "大量泄漏", "一直漏气", "严重漏气", "管道破裂", "管道裂了",
    "阀门关不上", "漏气止不住", "管子破了",
    "昏迷", "没有呼吸", "心跳停止", "中毒严重", "人不行了",
    "烧伤", "烫伤严重", "有人受伤",
    "中毒", "一氧化碳",
]

LEVEL2_REPLY = """检测到可能存在燃气安全风险。

**【请立即检查】**
1. 打开门窗，保持室内通风
2. 用肥皂水涂抹管道接口处，观察是否有气泡（有气泡=泄漏）
3. 如确认有泄漏或持续闻到异味，请立即关闭燃气总阀门

如需进一步排查，请拨打 24 小时燃气抢修电话：**0734-8677777**"""

LEVEL3_REPLY = """检测到可能存在燃气安全风险。

**请立即：**
1. 关闭燃气总阀门
2. 打开窗户通风
3. 不要使用明火
4. 不要开关任何电器
5. 迅速离开危险区域

请立即拨打 24 小时燃气抢修电话：**0734-8677777**"""


def _is_safe_context(question: str) -> bool:
    for pattern in SAFE_CONTEXTS:
        if re.search(pattern, question):
            return True
    return False


def detect_emergency(question: str) -> dict:
    if _is_safe_context(question):
        return {"level": 1, "is_emergency": False, "risk_label": "普通",
                "matched": [], "reply": "", "reason": "安全语境（故障咨询）", "action": "正常回答"}

    matched_3 = [kw for kw in LEVEL3_KEYWORDS if kw in question]
    if matched_3:
        return {"level": 3, "is_emergency": True, "risk_label": "高危",
                "matched": matched_3, "reply": LEVEL3_REPLY,
                "reason": f"命中高危关键词: {', '.join(matched_3)}",
                "action": "红色警报 + 自动工单 + 强制转人工"}

    matched_2 = [kw for kw in LEVEL2_KEYWORDS if kw in question]
    if matched_2:
        return {"level": 2, "is_emergency": True, "risk_label": "疑似风险",
                "matched": matched_2, "reply": LEVEL2_REPLY,
                "reason": f"命中疑似关键词: {', '.join(matched_2)}",
                "action": "黄色提醒 + 安全建议 + 推荐人工"}

    return {"level": 1, "is_emergency": False, "risk_label": "普通",
            "matched": [], "reply": "", "reason": "普通业务问题", "action": "正常回答"}


def generate_ticket(question: str, risk_level: str, ip: str = "", user_id: str = "") -> dict:
    from db import add_ticket
    import uuid
    ticket_id = f"EM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    return add_ticket(ticket_id, question, risk_level, ip, user_id)


def log_emergency(question: str, risk_level: str, ip: str = "", ticket_id: str = ""):
    from db import add_emergency_log
    add_emergency_log(question, risk_level, ip, ticket_id)
