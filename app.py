"""
衡阳市天然气AI客服智能体 — 六层管道架构
用户输入 → 意图理解AI → 分类检索 → 客服回答AI → 风险识别AI → 工单AI → 后台
"""
from flask import Flask, render_template, request, jsonify, session, redirect
from config import SECRET_KEY, DEBUG, ENABLE_AI_FALLBACK
from services.knowledge_service import KnowledgeService
from services.ai_service import (
    AIService, IntentDetector, IntentUnderstandingService, RiskDetectionService,
    TicketGenerationService,
    REJECT_REPLY, GREETING_REPLY, IDENTITY_REPLY, BUSINESS_GUIDE_REPLY,
    REFUND_REPLY, EMOTION_REPLY, EMOTION_LIGHT_REPLY, CRISIS_REPLY, COMPLAINT_REPLY,
)
from services.emergency import detect_emergency, generate_ticket, log_emergency
import os, csv, pandas as pd

app = Flask(__name__)
app.secret_key = SECRET_KEY

kb = KnowledgeService()
ai = AIService() if ENABLE_AI_FALLBACK else None
intent_svc = IntentUnderstandingService(ai._client) if ai else None
risk_svc = RiskDetectionService(ai._client) if ai else None
ticket_svc = TicketGenerationService(ai._client) if ai else None

TRANSFER_REPLY = (
    "非常抱歉，我暂时无法准确回答您的问题。"
    "建议您拨打衡阳市天然气有限责任公司24小时客服热线 "
    "**0734-8222222** 转人工客服，"
    "或前往就近营业厅咨询。"
)


@app.route("/")
def index():
    return render_template("index.html")


# ══════════════════════════════════════════════════════
# 六层管道架构
# 用户输入 → 意图理解 → 分类检索 → 客服回答 → 风险识别 → 工单 → 后台
# ══════════════════════════════════════════════════════

# ── 快速意图 → 回复映射表 ──────────────────────
FAST_INTENT_REPLIES = {
    "crisis":    (CRISIS_REPLY,        "crisis",    "紧急干预 > 心理安抚"),
    "abuse":     (EMOTION_LIGHT_REPLY, "emotion",   "情绪安抚 > 轻度引导"),
    "nonsense":  ("您好，请问您遇到了什么燃气问题？我可以帮您查询或办理相关业务。", "guide", "业务引导 > 无意义输入"),
    "emotion":   (EMOTION_REPLY,       "emotion",   "情绪安抚 > 用户情绪疏导"),
    "complaint": (COMPLAINT_REPLY,     "complaint", "投诉建议 > 投诉受理"),
    "greeting":  (GREETING_REPLY,      "greeting",  "智能欢迎 > 问候"),
    "identity":  (IDENTITY_REPLY,      "identity",  "智能欢迎 > 身份介绍"),
    "irrelevant":(REJECT_REPLY,        "reject",    "转人工 > 超出范围"),
}


def _layer1_intent(question: str) -> dict:
    """
    Layer 1 — 意图理解 AI
    正则快速过滤 + LLM 深度理解
    返回: {fast_return, response?, regex_intent, llm_intent?}
    """
    regex_intent = IntentDetector.detect(question)

    # 快速路径：非业务意图直接返回
    if regex_intent in FAST_INTENT_REPLIES:
        reply, source, category = FAST_INTENT_REPLIES[regex_intent]
        return {
            "fast_return": True,
            "response": jsonify({"reply": reply, "source": source, "category": category}),
            "regex_intent": regex_intent,
        }

    # 业务意图：LLM 深度理解
    llm = None
    if intent_svc:
        llm = intent_svc.understand(question)

    return {
        "fast_return": False,
        "regex_intent": regex_intent,
        "llm_intent": llm,
        "standard_question": llm["standard_question"] if llm else question,
        "category": llm["category"] if llm else kb._classify(question),
        "real_intent": llm["real_intent"] if llm else question,
    }


def _layer2_search(standard_question: str, original_question: str) -> dict:
    """
    Layer 2 — 分类检索
    FAQ 优先 → 法规兜底 → Top-K RAG 召回
    返回: {faq, policy, top_k, best_score}
    """
    # FAQ 搜索（先用标准问题，再用原始问题）
    faq = kb.search_faq(standard_question)
    if not faq and standard_question != original_question:
        faq = kb.search_faq(original_question)

    # 法规搜索
    policy = kb.search_policy(standard_question)
    if not policy and standard_question != original_question:
        policy = kb.search_policy(original_question)

    # Top-K RAG 召回
    top_k = kb.search_top_k(standard_question, k=8)

    # 最佳匹配分
    best_score = faq["score"] if faq else (top_k[0]["score"] if top_k else 0.0)

    return {
        "faq": faq,
        "policy": policy,
        "top_k": top_k,
        "best_score": best_score,
    }


def _layer3_reply(question: str, search: dict, intent: dict,
                  history: list = None) -> dict:
    """
    Layer 3 — 客服回答 AI
    FAQ 命中快速路径 → RAG+AI 兜底 → 业务模板路由
    返回: {text, source, category, ...}
    """
    # 快速路径：FAQ 命中
    if search["faq"]:
        f = search["faq"]
        return {
            "text": f["answer"],
            "source": "faq",
            "category": f["category"],
            "match_question": f["question"],
            "score": f["score"],
            "law_basis": f.get("law", ""),
            "law_code": f.get("law_code", ""),
        }

    # 快速路径：法规命中
    if search["policy"]:
        p = search["policy"]
        return {
            "text": p["answer"],
            "source": "policy",
            "category": p["category"],
            "match_question": p["question"],
            "score": p["score"],
            "law_basis": p.get("law", ""),
            "law_code": p.get("law_code", ""),
        }

    # 模板路由：退款 / 转人工
    ri = intent["regex_intent"]
    if ri == "refund":
        return {"text": REFUND_REPLY, "source": "refund", "category": "气费管理 > 退款申请"}
    if ri == "transfer":
        return {"text": TRANSFER_REPLY, "source": "transfer", "category": "转人工 > 用户要求"}

    # AI 兜底：RAG + DeepSeek
    if ai:
        top_k = search["top_k"]
        ai_reply = ai.ask_with_rag(
            question=question,
            kb_contexts=top_k,
            history=history,
            standard_question=intent.get("standard_question", ""),
            category=intent.get("category", ""),
            match_score=search["best_score"],
        )
        if ai_reply:
            return {
                "text": ai_reply,
                "source": "ai_rag",
                "category": intent.get("category", ""),
                "rag_count": len(top_k),
            }

    # 最终兜底：业务引导
    return {
        "text": BUSINESS_GUIDE_REPLY,
        "source": "guide",
        "category": intent.get("category", "业务引导 > 知识库未命中"),
    }


def _layer4_risk(question: str, reply_text: str) -> dict:
    """
    Layer 4 — 风险识别 AI
    对 问题 + 回答 做安全审查，防漏判
    返回: {risk_level, risk_label, needs_ticket, risk_reason, safety_appended, final_reply}
    """
    result = {
        "risk_level": 1,
        "risk_label": "普通",
        "needs_ticket": False,
        "risk_reason": "",
        "safety_appended": False,
        "final_reply": reply_text,
    }

    # 关键词快速扫描
    kw_emergency = detect_emergency(question)

    # Level 2/3 关键词命中：追加安全提醒
    if kw_emergency["level"] >= 2:
        result["risk_level"] = kw_emergency["level"]
        result["risk_label"] = kw_emergency["risk_label"]
        result["risk_reason"] = kw_emergency.get("reason", "")
        result["needs_ticket"] = kw_emergency["level"] == 3
        # 回答中如果没有安全提醒，自动追加
        safety_prefix = kw_emergency.get("reply", "")
        if safety_prefix and safety_prefix not in reply_text:
            result["final_reply"] = safety_prefix + "\n\n" + reply_text
            result["safety_appended"] = True
        return result

    # LLM 深度审查（关键词未命中时兜底）
    if risk_svc and kw_emergency["level"] == 1:
        comparison = risk_svc.compare_with_keyword(question, kw_emergency)
        if comparison["verdict"] == "llm_upgrade":
            llm = comparison["llm_risk"]
            result["risk_level"] = comparison["final_level"]
            result["risk_label"] = comparison["final_level_label"]
            result["risk_reason"] = llm.get("risk_reason", "") if llm else ""
            result["needs_ticket"] = comparison["final_level"] >= 3

    return result


def _layer5_ticket(question: str, risk: dict, client_ip: str = "") -> dict | None:
    """
    Layer 5 — 工单 AI
    仅当风险等级 >= 中危时生成工单
    返回: ticket dict 或 None
    """
    if not risk["needs_ticket"] and risk["risk_level"] < 2:
        return None

    # 用户标识
    user_session = session.get("user_id", "")
    if not user_session:
        import uuid
        user_session = uuid.uuid4().hex[:12]
        session["user_id"] = user_session

    # 关键词工单（快速落库）
    ticket = generate_ticket(question, risk["risk_label"], client_ip, user_session)
    log_emergency(question, risk["risk_label"], client_ip, ticket["工单ID"])

    # LLM 工单（富文本）
    llm_ticket = None
    if ticket_svc:
        llm_ticket = ticket_svc.generate(question, risk)

    return {
        "keyword_ticket": ticket,
        "llm_ticket": llm_ticket,
    }


def _layer6_build_response(reply: dict, intent: dict, search: dict,
                           risk: dict, ticket: dict | None) -> dict:
    """
    Layer 6 — 组装最终响应
    """
    resp = {
        "reply": risk.get("final_reply", reply["text"]),
        "source": reply.get("source", "guide"),
        "category": reply.get("category", ""),
        # 意图理解
        "intent": {
            "regex_intent": intent["regex_intent"],
            "real_intent": intent.get("real_intent", ""),
            "standard_question": intent.get("standard_question", ""),
            "category": intent.get("category", ""),
        },
        # 检索信息
        "search": {
            "faq_hit": search["faq"] is not None,
            "policy_hit": search["policy"] is not None,
            "best_score": search["best_score"],
        },
        # 风险信息
        "risk": {
            "level": risk["risk_level"],
            "label": risk["risk_label"],
            "reason": risk["risk_reason"],
            "safety_appended": risk["safety_appended"],
        },
    }
    if reply.get("match_question"):
        resp["match_question"] = reply["match_question"]
    if reply.get("score"):
        resp["score"] = reply["score"]
    if reply.get("law_basis"):
        resp["law_basis"] = reply["law_basis"]
        resp["law_code"] = reply.get("law_code", "")
    if reply.get("rag_count"):
        resp["rag_count"] = reply["rag_count"]
    if ticket:
        resp["ticket"] = ticket["keyword_ticket"]["工单ID"] if ticket.get("keyword_ticket") else None
        resp["llm_ticket"] = ticket.get("llm_ticket")
    return resp


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    history = data.get("history", [])
    client_ip = request.remote_addr or ""

    # Layer 1: 意图理解 AI
    intent = _layer1_intent(question)
    if intent["fast_return"]:
        return intent["response"]

    # Layer 2: 分类检索
    search = _layer2_search(intent["standard_question"], question)

    # Layer 3: 客服回答 AI
    reply = _layer3_reply(question, search, intent, history)

    # Layer 4: 风险识别 AI
    risk = _layer4_risk(question, reply["text"])

    # Layer 5: 工单 AI
    ticket = _layer5_ticket(question, risk, client_ip)

    # Layer 6: 返回响应
    response = _layer6_build_response(reply, intent, search, risk, ticket)
    return jsonify(response)


# ── 管理后台（Session密码保护）────────────────
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "hygas0826")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template("admin_login.html", error="密码错误")
    return render_template("admin_login.html", error="")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")

def _check_admin():
    return session.get("admin", False)

@app.route("/admin")
def admin():
    if not _check_admin():
        return redirect("/admin/login")
    # 读取统计数据
    from config import KB_FAQ_PATH, KB_POLICY_PATH, TAG_SYSTEM_PATH
    faq_count = 0
    policy_count = 0
    try:
        faq_df = pd.read_csv(KB_FAQ_PATH, encoding="utf-8-sig")
        faq_count = len(faq_df)
    except: pass
    try:
        pol_df = pd.read_csv(KB_POLICY_PATH, encoding="utf-8-sig")
        policy_count = len(pol_df)
    except: pass

    # 读取工单
    tickets = []
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            tickets = list(reader)[-20:]
    except: pass

    # 读取日志
    logs = []
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "emergency.log")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            logs = f.readlines()[-20:]
    except: pass

    return render_template("admin.html",
        faq_count=faq_count, policy_count=policy_count,
        tickets=tickets, logs=logs)


@app.route("/admin/reload", methods=["POST"])
def admin_reload():
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    try:
        kb.reload()
        return jsonify({"status": "ok", "message": "知识库已重新加载"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    """上传Excel更新知识库"""
    from config import KB_FAQ_PATH
    file = request.files.get("file")
    if not file or not file.filename.endswith((".xlsx", ".csv")):
        return jsonify({"status": "error", "message": "请上传.xlsx或.csv文件"}), 400

    filepath = KB_FAQ_PATH
    if file.filename.endswith(".csv"):
        file.save(filepath)
    else:
        file.save(filepath.replace(".csv", ".xlsx"))

    try:
        kb.reload()
        return jsonify({"status": "ok", "message": "知识库已更新并重新加载"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/tickets/clear", methods=["POST"])
def admin_tickets_clear():
    """清除全部工单"""
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    try:
        tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        with open(tickets_path, "w", encoding="utf-8-sig") as f:
            f.write("工单ID,时间,用户问题,风险等级,分类,状态,用户IP\n")
        return jsonify({"status": "ok", "message": "全部工单已清除"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin/tickets/resolve/<ticket_id>", methods=["POST"])
def admin_tickets_resolve(ticket_id):
    """标记工单为已解决（不删除，用户可见）"""
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    try:
        tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        rows = []
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get("工单ID") == ticket_id:
                    row["状态"] = "已解决"
                rows.append(row)
        with open(tickets_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return jsonify({"status": "ok", "message": f"工单 {ticket_id} 已标记为已解决"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/my-tickets")
def my_tickets():
    """用户查看自己的工单"""
    user_id = session.get("user_id", "")
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    my = []
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("用户标识") == user_id:
                    my.append(row)
    except: pass
    return render_template("my_tickets.html", tickets=my)

@app.route("/admin/tickets")
def admin_tickets():
    """查看工单"""
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    tickets = []
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            tickets = list(csv.DictReader(f))
    except: pass
    return jsonify(tickets)


@app.route("/api/intent", methods=["POST"])
def analyze_intent():
    """用户意图理解接口 — LLM深度语义理解"""
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    if not intent_svc:
        return jsonify({"error": "AI服务未启用，请设置 DEEPSEEK_API_KEY"}), 503

    # 先跑正则意图（快速）
    regex_intent = IntentDetector.detect(question)

    # LLM深度理解
    result = intent_svc.understand(question)

    return jsonify({
        "question": question,
        "regex_intent": regex_intent,
        "llm_intent": result,
    })


@app.route("/api/risk", methods=["POST"])
def analyze_risk():
    """风险识别接口 — LLM + 关键词规则对比"""
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    if not risk_svc:
        return jsonify({"error": "AI服务未启用，请设置 DEEPSEEK_API_KEY"}), 503

    # 关键词规则
    keyword_result = detect_emergency(question)
    # LLM + 对比
    comparison = risk_svc.compare_with_keyword(question, keyword_result)

    return jsonify({
        "question": question,
        "keyword_risk": comparison["keyword_risk"],
        "llm_risk": comparison["llm_risk"],
        "verdict": comparison["verdict"],
        "final_level": comparison["final_level"],
        "final_level_label": comparison["final_level_label"],
    })


@app.route("/api/ticket", methods=["POST"])
def generate_ticket_api():
    """工单生成接口 — LLM生成标准工单"""
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    if not ticket_svc or not risk_svc:
        return jsonify({"error": "AI服务未启用，请设置 DEEPSEEK_API_KEY"}), 503

    # 先跑风险识别
    risk = risk_svc.compare_with_keyword(question, detect_emergency(question))
    # LLM 生成工单
    llm_ticket = ticket_svc.generate(question, risk)

    return jsonify({
        "question": question,
        "risk_summary": {
            "final_level": risk["final_level_label"],
            "verdict": risk["verdict"],
        },
        "llm_ticket": llm_ticket,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=DEBUG, host="0.0.0.0", port=port)
