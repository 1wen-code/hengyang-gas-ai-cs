"""
衡阳市天然气AI客服智能体 — 三级风险判断系统
一级(普通) = 正常回答  二级(疑似) = 黄色提醒  三级(高危) = 红色警报+工单
"""
import csv, os, uuid, re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKETS_PATH = os.path.join(BASE_DIR, "logs", "tickets.csv")
EMERGENCY_LOG_PATH = os.path.join(BASE_DIR, "logs", "emergency.log")
os.makedirs(os.path.dirname(TICKETS_PATH), exist_ok=True)

# ── 安全词：含这些词的提问降级为普通 ──────────
SAFE_CONTEXTS = [
    "打不着", "打不燃", "点不着", "打不着火", "打不燃火",
    "没热水", "不出热水", "热水器.*不",
    "火焰.*小", "火.*小", "火苗.*小",
    "电池", "没电", "欠费", "充值",
    "怎么.*修", "排查", "怎么办", "怎么回事",
    "为什么", "什么原因", "如何", "怎样",
    "不着火", "点不燃", "不打火",
]

# ── 一级(普通)：正常业务问题 ──────────────────
# 不触发任何警报，走标准FAQ/AI流程
LEVEL1_KEYWORDS = [
    "没热水", "打不着火", "火焰小", "红火", "黄火",
    "电池没电", "电池更换", "换电池", "欠费停气",
    "IC卡充值", "余额不足", "充值不到账",
]

# ── 二级(疑似风险)：黄色提醒 ──────────────────
LEVEL2_KEYWORDS = [
    "闻到煤气味", "闻到燃气味", "有煤气味", "有燃气味",
    "刺鼻气味", "异味", "臭味", "像漏气",
    "疑似漏气", "怀疑漏气", "可能漏气",
    "轻微泄漏", "一点点泄漏",
    "报警器", "燃气表一直走",
    "头晕", "恶心", "不舒服", "胸闷",
    "燃气味", "煤气味",
    "燃气泄漏", "漏气",
]

# ── 三级(高危紧急)：红色警报 ───────────────────
LEVEL3_KEYWORDS = [
    "爆炸", "爆燃", "炸了", "着火", "起火", "火灾", "明火",
    "大量泄漏", "一直漏气", "严重漏气", "管道破裂", "管道裂了",
    "阀门关不上", "漏气止不住", "管子破了",
    "昏迷", "没有呼吸", "心跳停止", "中毒严重", "人不行了",
    "烧伤", "烫伤严重", "有人受伤",
]

# ── 回复模板 ──────────────────────────────────

LEVEL2_REPLY = """⚠ 感谢您的反馈。根据您的描述，建议您进行以下检查：

**【安全提醒】**
1. 打开门窗，保持室内通风
2. 用肥皂水涂抹管道接口处，观察是否有气泡（有气泡=泄漏）
3. 如确认有泄漏或持续闻到异味，请立即关闭燃气总阀

**【建议】**
如需进一步排查，建议拨打客服热线 **0734-8677777** 预约专业人员上门检测。

请您注意安全，如有任何异常请随时联系我们。"""

LEVEL3_REPLY = """⚠ 检测到燃气安全紧急事件，请您立即执行以下应急措施：

**【紧急处置】**
1. 立即关闭燃气总阀（顺时针旋转到底）
2. 打开所有门窗通风
3. 严禁开关任何电器、使用手机（在泄漏区域内）、动用明火
4. 迅速撤离到室外安全区域

**【系统已强制转人工】**
紧急抢修电话：**0734-8677777**
消防报警电话：**119**

请保持电话畅通，安全专员将立即与您联系。"""


def _is_safe_context(question: str) -> bool:
    """判断是否为安全语境（普通故障咨询，非紧急）"""
    for pattern in SAFE_CONTEXTS:
        if re.search(pattern, question):
            return True
    return False


def detect_emergency(question: str) -> dict:
    """
    三级风险检测。
    返回: {level: 1|2|3, is_emergency: bool, reply: str, matched: [...], reason: str}
    """
    # Step 0: 安全语境检查（对所有级别生效）
    if _is_safe_context(question):
        return {"level": 1, "is_emergency": False, "risk_label": "普通", "matched": [], "reply": "", "reason": "安全语境（故障咨询）", "action": "正常回答"}

    # Step 1: 检查三级（高危）
    matched_3 = [kw for kw in LEVEL3_KEYWORDS if kw in question]
    if matched_3:
        return {
            "level": 3, "is_emergency": True,
            "risk_label": "高危", "matched": matched_3,
            "reply": LEVEL3_REPLY,
            "reason": f"命中高危关键词: {', '.join(matched_3)}",
            "action": "红色警报 + 自动工单 + 强制转人工",
        }

    # Step 2: 检查二级（疑似风险）
    matched_2 = [kw for kw in LEVEL2_KEYWORDS if kw in question]
    if matched_2:
        return {
            "level": 2, "is_emergency": True,
            "risk_label": "疑似风险", "matched": matched_2,
            "reply": LEVEL2_REPLY,
            "reason": f"命中疑似关键词: {', '.join(matched_2)}",
            "action": "黄色提醒 + 安全建议 + 推荐人工",
        }

    # Step 3: 一级（普通）
    return {"level": 1, "is_emergency": False, "risk_label": "普通", "matched": [], "reply": "", "reason": "普通业务问题", "action": "正常回答"}


def generate_ticket(question: str, risk_level: str, ip: str = "", user_session: str = "") -> dict:
    """生成紧急工单（仅三级高危）"""
    ticket_id = f"EM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = {
        "工单ID": ticket_id, "时间": created_at,
        "用户问题": question, "风险等级": risk_level,
        "分类": "紧急事件", "状态": "处理中", "用户IP": ip,
        "用户标识": user_session,
    }
    os.makedirs(os.path.dirname(TICKETS_PATH), exist_ok=True)
    file_exists = os.path.exists(TICKETS_PATH)
    with open(TICKETS_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ticket.keys())
        if not file_exists: writer.writeheader()
        writer.writerow(ticket)
    return ticket


def log_emergency(question: str, risk_level: str, ip: str = "", ticket_id: str = ""):
    """写入日志（二级+三级）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EMERGENCY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{risk_level}] IP={ip} TICKET={ticket_id} Q={question}\n")
