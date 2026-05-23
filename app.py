"""
衡阳市天然气AI客服智能体 — 六层管道架构
用户输入 → 意图理解AI → 分类检索 → 客服回答AI → 风险识别AI → 工单AI → 后台
"""
from flask import Flask, render_template, request, jsonify, session, redirect
from config import SECRET_KEY, DEBUG, ENABLE_AI_FALLBACK
from services.knowledge_service import KnowledgeService
from services.understand_service import UnderstandService
from services.ai_service import (
    AIService, IntentDetector, IntentUnderstandingService, RiskDetectionService,
    TicketGenerationService, IntentClassifierService, EmotionDetectionService, FuzzyDetectionService, SessionStateService,
    REJECT_REPLY, GREETING_REPLY, IDENTITY_REPLY, BUSINESS_GUIDE_REPLY,
    REFUND_REPLY, EMOTION_REPLY, EMOTION_LIGHT_REPLY, CRISIS_REPLY, COMPLAINT_REPLY,
)
from services.emergency import detect_emergency, generate_ticket, log_emergency
from services.ai_service import FUZZY_MAP, OVER_ASSOCIATION_BLOCK
import os, csv, pandas as pd

app = Flask(__name__)
app.secret_key = SECRET_KEY

kb = KnowledgeService()
ai = AIService() if ENABLE_AI_FALLBACK else None
intent_svc = IntentUnderstandingService(ai._client) if ai else None
risk_svc = RiskDetectionService(ai._client) if ai else None
ticket_svc = TicketGenerationService(ai._client) if ai else None
classifier_svc = IntentClassifierService(ai._client) if ai else None
emotion_svc = EmotionDetectionService(ai._client) if ai else None
fuzzy_svc = FuzzyDetectionService(ai._client) if ai else None
understand_svc = UnderstandService(ai._client) if ai else None
state_svc = SessionStateService(ai._client) if ai else None

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
# 十一层管道架构
# 用户输入 → 状态机判断 → 风险模块 → 模糊语义 → 意图分类 → RAG检索 → Answer生成
# → 业务状态 → 是否RAG → 检索 → 相似度过滤 → DeepSeek生成
# → 工单生成 → 后台管理
# ══════════════════════════════════════════════════════

# ── 历史格式化工具 ──────────────────────────────
def _fmt_history(history: list, max_items: int = 6) -> str:
    if not history:
        return "（无历史记录）"
    lines = []
    for h in history[-max_items:]:
        role = "用户" if h.get("role") == "user" else "客服"
        content = h.get("content", "")[:100]
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


# ── 快速路径映射 ────────────────────────────────
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


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400
    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400
    client_history = data.get("history", [])
    client_ip = request.remote_addr or ""

    
    history = []  # 初始化，后续在上下文记忆中赋值
    # === 0. 状态机优先判断 ===
    try:
        conversation_state = session.get("conversation_state", {}) or {}
    except:
        conversation_state = {}
    if not isinstance(conversation_state, dict):
        conversation_state = {}

    awaiting_option = conversation_state.get("awaiting_option", False)
    fault_type = conversation_state.get("fault_type", "")
    safe_confirm_count = conversation_state.get("safe_confirm_count", 0)

    # 状态锁：等待用户选择选项时，直接解析选项编号
    if awaiting_option and question.strip() in ["1", "2", "3", "4", "5"]:
        option = int(question.strip())
        session["conversation_state"] = {
            "awaiting_option": False,
            "fault_type": fault_type,
            "risk_active": conversation_state.get("risk_active", False),
            "safe_confirm_count": safe_confirm_count,
            "last_option_selected": option,
        }
        # 把选项编号转为语义传给管道
        question = f"用户选择了第{option}个选项（上一轮故障类型：{fault_type}）"

    # 风险冷却机制：需要连续2次安全确认才能解除风险
    risk_active = conversation_state.get("risk_active", False)
    risk_locked = bool(session.get("risk_locked", False) or risk_active)
    safety_confirm_words = ["没味了", "没味道了", "关了", "关好了", "通风了", "不晕了",
                            "修好了", "换好了", "正常了", "解决了", "没事了", "好了"]
    safety_count = sum(1 for w in safety_confirm_words if w in question)

    if risk_active and safety_count >= 1:
        safe_confirm_count += 1
        if safe_confirm_count >= 2:
            risk_active = False
            safe_confirm_count = 0
    elif not risk_active:
        safe_confirm_count = 0

    session["conversation_state"] = {
        "awaiting_option": awaiting_option,
        "fault_type": fault_type,
        "risk_active": risk_active,
        "safe_confirm_count": safe_confirm_count,
    }

    # 模糊词替换：方言口语 → 标准故障标签
    fuzzy_hits = []
    for fuzzy_word, standard_label in FUZZY_MAP.items():
        if fuzzy_word in question:
            fuzzy_hits.append(standard_label)
    if fuzzy_hits:
        question = question + "（系统识别口语含义：" + "、".join(fuzzy_hits) + "）"

    # 过度联想检查：单症状不能判泄漏
    over_assoc_warn = ""
    for symptom, rule in OVER_ASSOCIATION_BLOCK.items():
        if symptom in question:
            has_required = any(req in question for req in rule["requires"])
            # Also check history
            if history:
                for h in history:
                    if h.get("role") == "user" and any(req in h.get("content", "") for req in rule["requires"]):
                        has_required = True
                        break
            if not has_required:
                over_assoc_warn = f"（注意：{rule['block_reason']}）"
                question = question + over_assoc_warn

# === 1. 上下文记忆 ===
    server_memory = session.get("conversation_memory", [])
    seen = set()
    merged = []
    for m in server_memory + client_history:
        k = (m.get("role",""), m.get("content","")[:80])
        if k not in seen:
            seen.add(k); merged.append(m)
    history = merged[-20:]
    chat_context = _fmt_history(history)

    # === 1.5 UNDERSTAND 语义归一化 ===
    understand = {"normalized_intent": question, "possible_scene": "", "risk_hint": "none", "emotion": ""}
    if understand_svc:
        try:
            result = understand_svc.normalize(question, chat_context)
            if result and result.get("normalized_intent"):
                understand = result
                if understand["normalized_intent"] != question:
                    question = understand["normalized_intent"]
        except:
            pass

    # === 1b. 快速过滤 ===
    regex_intent = IntentDetector.detect(question)
    if regex_intent in FAST_INTENT_REPLIES:
        reply, source, category = FAST_INTENT_REPLIES[regex_intent]
        return jsonify({"reply": reply, "source": source, "category": category})

        # 过度联想检查（在历史记录可用之后）
    over_assoc_warn = ""
    for symptom, rule in OVER_ASSOCIATION_BLOCK.items():
        if symptom in question:
            has_required = any(req in question for req in rule["requires"])
            if history:
                for h in history:
                    if h.get("role") == "user" and any(req in h.get("content", "") for req in rule["requires"]):
                        has_required = True
                        break
            if not has_required:
                question = question + f"（注意：{rule['block_reason']}）"

    # === 2. 意图分类 ===
    if classifier_svc:
        classification = classifier_svc.classify(question, chat_context)
    else:
        classification = {"is_gas_related": True, "need_rag": True, "category": "", "risk_level": "", "confidence": 0.5}
    if not classification.get("is_gas_related", True):
        return jsonify({"reply": REJECT_REPLY, "source": "reject", "category": "闲聊无关", "classification": classification})

    # === 3. 情绪识别 ===
    emotion = {"emotion": "calm", "intensity": 0, "need_calm_first": False, "tone_suggestion": "正常回答"}
    if emotion_svc:
        emotion = emotion_svc.detect(question, chat_context)

    # === 4. 风险识别 ===
    risk = {"level": 1, "label": "普通", "needs_ticket": False, "reason": "", "safety_prefix": ""}
    kw = detect_emergency(question)
    if kw["level"] >= 2:
        risk = {"level": kw["level"], "label": kw["risk_label"], "needs_ticket": kw["level"] == 3, "reason": kw.get("reason",""), "safety_prefix": kw.get("reply","")}
    elif risk_svc:
        comp = risk_svc.compare_with_keyword(question, kw)
        if comp["verdict"] == "llm_upgrade":
            risk = {"level": comp["final_level"], "label": comp["final_level_label"], "needs_ticket": comp["final_level"] >= 3, "reason": comp.get("llm_risk",{}).get("risk_reason","") if comp.get("llm_risk") else "", "safety_prefix": ""}

    # === 4.5 会话状态机 ===
    prev_state = session.get("conversation_state", "normal")
    state_result = state_svc.evaluate(question, prev_state, risk["label"]) if state_svc else {"new_state": "normal", "should_confirm_safety": False, "safety_reminder": ""}
    session["conversation_state"] = state_result.get("new_state", "normal")

    # 高危状态恢复检查：如果上一轮是危险状态且用户说没事了，追加安全提醒
    safety_append = ""
    if state_result.get("should_confirm_safety") and state_result.get("safety_reminder"):
        safety_append = state_result["safety_reminder"]

    # === 5. 业务状态判断 ===
    biz = {"standard_question": question, "category": classification.get("category",""), "real_intent": question}
    if intent_svc:
        llm = intent_svc.understand(question)
        if llm:
            biz = {"standard_question": llm.get("standard_question", question), "category": llm.get("category", classification.get("category","")), "real_intent": llm.get("real_intent", question)}

    # === 6. 是否RAG + 7. 检索 ===
    search = {"faq": None, "policy": None, "top_k": [], "best_score": 0.0}
    if classification.get("need_rag", True):
        sq = biz["standard_question"]
        search["faq"] = kb.search_faq(sq)
        if not search["faq"] and sq != question:
            search["faq"] = kb.search_faq(question)
        search["policy"] = kb.search_policy(sq)
        if not search["policy"] and sq != question:
            search["policy"] = kb.search_policy(question)
        search["top_k"] = kb.search_top_k(sq, k=8)
        search["best_score"] = search["faq"]["score"] if search["faq"] else (search["top_k"][0]["score"] if search["top_k"] else 0.0)

    # === 8. 相似度过滤 + 类别一致性 + AI自主判断 ===
    faq_ok = search["faq"] and search["faq"]["score"] >= 0.20

    if faq_ok:
        cls_cat = classification.get("category", "")
        cls_conf = classification.get("confidence", 0)
        faq_cat = search["faq"]["category"] if search["faq"] else ""
        faq_score = search["faq"]["score"]

        # 危险类别对：直接拒绝
        danger_pairs = [
            ("燃气泄漏", "燃气缴费"), ("燃气泄漏", "开户安装"),
            ("安全用气", "燃气缴费"), ("安全用气", "开户安装"),
            ("燃气缴费", "安全用气"), ("燃气缴费", "燃气泄漏"),
            ("开户安装", "安全用气"), ("开户安装", "燃气泄漏"),
            ("灶具维修", "燃气泄漏"), ("热水器故障", "燃气泄漏"),
        ]
        mismatch = any(
            (a in cls_cat and b in faq_cat) or (b in cls_cat and a in faq_cat)
            for a, b in danger_pairs
        )
        if mismatch:
            faq_ok = False

        # 回复相关性检查：FAQ答案与用户问题场景不匹配时降级
        if faq_ok:
            faq_ans = search["faq"]["answer"] if search["faq"] else ""
            faq_q = search["faq"]["question"] if search["faq"] else ""
            understand_scene = understand.get("possible_scene", "")

            # 模板型/不相关答案关键词
            vague_patterns = ["准备什么", "维修师傅", "预约", "签验收", "锅底发黑", "锅底", "烧黑"]
            if any(p in faq_ans or p in faq_q for p in vague_patterns):
                faq_ok = False

            # UNDERSTAND场景与FAQ问题场景不一致
            scene_mismatch = [
                ("热水器", "灶"), ("灶", "热水器"),
                ("热水器", "锅"), ("灶", "锅"),
            ]
            for a, b in scene_mismatch:
                if a in understand_scene and b in faq_q:
                    faq_ok = False
                    break

        # AI自主判断：分类器高置信 + FAQ低分 → 让AI自己思考
        if faq_ok and cls_conf >= 0.80 and faq_score < 0.45:
            # 分类器很确定意图，但 FAQ 匹配度偏低，可能是知识库没有精确匹配
            # 让 AI 结合分类结果自主推理，不用模糊的 FAQ 回答
            faq_ok = False

    # === 8.5 模糊语义拦截 ===
    fuzzy = {"is_fuzzy": False, "reason": "", "suggested_question": ""}
    if fuzzy_svc:
        fuzzy = fuzzy_svc.detect(question)

    # === 9. DeepSeek生成 ===
    reply_text, reply_source, reply_meta = "", "guide", {}

    # 模糊描述：强制追问，不输出维修步骤
    if fuzzy.get("is_fuzzy"):
        fuzzy_r = None
        if ai:
            fuzzy_r = ai.ask_with_rag(question=question, kb_contexts=search["top_k"], history=history,
                                standard_question=biz["standard_question"], category=biz["category"],
                                match_score=0.0)
        if not fuzzy_r:
            fuzzy_r = fuzzy.get("suggested_question", "") or "请详细描述一下您遇到的问题，比如是什么设备、出现了什么现象？"
        reply_text, reply_source, reply_meta = fuzzy_r, "ai_rag", {"rag_count": len(search["top_k"]), "fuzzy_intercept": True}
    elif faq_ok:
        f = search["faq"]
        reply_text, reply_source = f["answer"], "faq"
        reply_meta = {"match_question": f["question"], "score": f["score"], "law_basis": f.get("law",""), "law_code": f.get("law_code","")}
    elif search["policy"]:
        p = search["policy"]
        reply_text, reply_source = p["answer"], "policy"
        reply_meta = {"match_question": p["question"], "score": p["score"], "law_basis": p.get("law",""), "law_code": p.get("law_code","")}
    elif ai:
        r = ai.ask_with_rag(question=question, kb_contexts=search["top_k"], history=history,
                            standard_question=biz["standard_question"], category=biz["category"],
                            match_score=search["best_score"])
        if r:
            reply_text, reply_source = r, "ai_rag"
            reply_meta = {"rag_count": len(search["top_k"])}
    if not reply_text:
        reply_text, reply_source = BUSINESS_GUIDE_REPLY, "guide"

    # 旧前端兼容：风险事件设置正确的source和追加安全提醒
    if risk["level"] >= 3:
        reply_source = "emergency"
    elif risk["level"] >= 2:
        reply_source = "warning"

    if risk["safety_prefix"] and risk["safety_prefix"] not in reply_text:
        reply_text = risk["safety_prefix"] + "\n\n" + reply_text

    # === 10. 工单生成 ===
    ticket = None
    if risk["needs_ticket"] or risk["level"] >= 2:
        uid = session.get("user_id", "")
        if not uid:
            import uuid; uid = uuid.uuid4().hex[:12]; session["user_id"] = uid
        kt = generate_ticket(question, risk["label"], client_ip, uid)
        log_emergency(question, risk["label"], client_ip, kt["工单ID"])
        lt = ticket_svc.generate(question, risk) if ticket_svc else None
        ticket = {"keyword_ticket": kt, "llm_ticket": lt}

    # === 11. 后台管理 ===
    server_memory.append({"role": "user", "content": question})
    server_memory.append({"role": "assistant", "content": reply_text})
    session["conversation_memory"] = server_memory[-20:]

    # 更新会话状态
    try:
        is_asking = any(q in reply_text for q in ["请问", "哪种", "哪个", "选", "1.", "2.", "①", "②"])
        st = conversation_state.copy() if isinstance(conversation_state, dict) else {}
        st["awaiting_option"] = is_asking
        st["fault_type"] = biz.get("category", fault_type)
        st["risk_active"] = risk_active or (isinstance(risk, dict) and risk.get("level", 0) >= 2)
        st["safe_confirm_count"] = safe_confirm_count
        session["conversation_state"] = st
    except:
        pass

    top1_score = search["top_k"][0]["score"] if search["top_k"] else 0.0
    resp = {
        "reply": reply_text, "source": reply_source, "category": biz["category"],
        # 旧格式兼容字段（前端还在用）
        "risk_level": risk.get("label", ""), "risk_code": risk.get("level", 1),
        "ticket_id": ticket["keyword_ticket"]["工单ID"] if ticket else None,
        "intent": {"regex_intent": regex_intent, "real_intent": biz["real_intent"],
                   "standard_question": biz["standard_question"], "category": biz["category"]},
        "emotion": emotion,
        "fuzzy": fuzzy,
        "understand": understand,
        "fuzzy": fuzzy,
        "understand": understand,
        "session_state": {"current": state_result.get("new_state", "normal"), "previous": prev_state, "should_confirm_safety": state_result.get("should_confirm_safety", False)},
        "session_state": {"current": state_result.get("new_state", "normal"), "previous": prev_state, "should_confirm_safety": state_result.get("should_confirm_safety", False)},
        "risk": {"level": risk["level"], "label": risk["label"], "reason": risk["reason"]},
        "classification": classification,
        "search": {"faq_hit": search["faq"] is not None, "policy_hit": search["policy"] is not None,
                   "best_score": search["best_score"], "top1_score": top1_score},
    }
    resp.update(reply_meta)
    if ticket:
        resp["ticket"] = ticket["keyword_ticket"]["工单ID"]
        resp["llm_ticket"] = ticket["llm_ticket"]
    return jsonify(resp)


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
