"""
衡阳市天然气AI客服智能体 — 主应用
流程：紧急检测 → 意图识别 → FAQ匹配 → 法规匹配 → RAG+DeepSeek → 业务引导 → 转人工
"""
from flask import Flask, render_template, request, jsonify
from config import SECRET_KEY, DEBUG, ENABLE_AI_FALLBACK
from services.knowledge_service import KnowledgeService
from services.ai_service import (
    AIService, IntentDetector,
    REJECT_REPLY, GREETING_REPLY, IDENTITY_REPLY, BUSINESS_GUIDE_REPLY,
)
from services.emergency import detect_emergency, generate_ticket, log_emergency
import os, csv, pandas as pd

app = Flask(__name__)
app.secret_key = SECRET_KEY

kb = KnowledgeService()
ai = AIService() if ENABLE_AI_FALLBACK else None

TRANSFER_REPLY = (
    "非常抱歉，我暂时无法准确回答您的问题。"
    "建议您拨打衡阳市天然气有限责任公司24小时客服热线 "
    "**0734-8677777** 转人工客服，"
    "或前往就近营业厅咨询。"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    client_ip = request.remote_addr or ""

    # ── Step 0: 三级风险检测 ────────────────────
    emergency = detect_emergency(question)

    if emergency["level"] == 3:
        # 高危：红色警报 + 工单 + 日志 + 强制转人工
        ticket = generate_ticket(question, emergency["risk_label"], client_ip)
        log_emergency(question, emergency["risk_label"], client_ip, ticket["工单ID"])
        return jsonify({
            "reply": emergency["reply"],
            "source": "emergency",
            "category": "紧急事件 > 高危",
            "risk_level": emergency["risk_label"],
            "risk_code": 3,
            "matched_keywords": emergency["matched"],
            "ticket_id": ticket["工单ID"],
        })

    if emergency["level"] == 2:
        # 疑似风险：黄色提醒 + 日志 + 推荐转人工（不强制）
        log_emergency(question, emergency["risk_label"], client_ip)
        return jsonify({
            "reply": emergency["reply"],
            "source": "warning",
            "category": "紧急事件 > 疑似风险",
            "risk_level": emergency["risk_label"],
            "risk_code": 2,
            "matched_keywords": emergency["matched"],
        })

    # Level 1（普通）：不拦截，继续走正常流程

    # ── Step 1: 意图识别 ──────────────────────
    intent = IntentDetector.detect(question)

    if intent == "greeting":
        return jsonify({
            "reply": GREETING_REPLY,
            "source": "greeting",
            "category": "智能欢迎 > 问候",
        })

    if intent == "identity":
        return jsonify({
            "reply": IDENTITY_REPLY,
            "source": "identity",
            "category": "智能欢迎 > 身份介绍",
        })

    if intent == "transfer":
        return jsonify({
            "reply": TRANSFER_REPLY,
            "source": "transfer",
            "category": "转人工 > 用户要求",
        })

    if intent == "vague_business":
        return jsonify({
            "reply": BUSINESS_GUIDE_REPLY,
            "source": "guide",
            "category": "业务引导 > 模糊咨询",
        })

    if intent == "irrelevant":
        return jsonify({
            "reply": REJECT_REPLY,
            "source": "reject",
            "category": "转人工 > 超出范围",
        })

    # ── Step 2: FAQ 精确匹配 ──────────────────
    faq_result = kb.search_faq(question)
    if faq_result:
        return jsonify({
            "reply": faq_result["answer"],
            "source": "faq",
            "category": faq_result["category"],
            "match_question": faq_result["question"],
            "score": faq_result["score"],
            "law_basis": faq_result.get("law", ""),
            "law_code": faq_result.get("law_code", ""),
        })

    # ── Step 3: 法规知识库匹配 ────────────────
    policy_result = kb.search_policy(question)
    if policy_result:
        return jsonify({
            "reply": policy_result["answer"],
            "source": "policy",
            "category": policy_result["category"],
            "match_question": policy_result["question"],
            "score": policy_result["score"],
            "law_basis": policy_result.get("law", ""),
            "law_code": policy_result.get("law_code", ""),
        })

    # ── Step 4: RAG + DeepSeek 兜底（多轮对话） ─
    if ai:
        # 获取会话历史
        history = data.get("history", [])
        top_k = kb.search_top_k(question, k=5)
        ai_reply = ai.ask_with_rag(question, top_k, history)
        if ai_reply:
            return jsonify({
                "reply": ai_reply,
                "source": "ai_rag",
                "category": kb._classify(question),
                "rag_count": len(top_k),
            })

    # ── Step 5: 业务引导兜底 ───────────────────
    return jsonify({
        "reply": BUSINESS_GUIDE_REPLY,
        "source": "guide",
        "category": "业务引导 > 知识库未命中",
    })


# ── 管理后台 ──────────────────────────────────
@app.route("/admin")
def admin():
    """管理后台页面"""
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
    """热更新知识库"""
    try:
        kb.reload()
        return jsonify({"status": "ok", "message": "知识库已重新加载"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=DEBUG, host="0.0.0.0", port=port)
