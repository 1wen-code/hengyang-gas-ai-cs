"""
衡阳市天然气AI客服 — Router + Session Mode + Handler 架构
所有消息：前端 → Flask → Router → Handler → 回复
"""
from flask import Flask, render_template, request, jsonify, session, redirect
from config import SECRET_KEY, DEBUG
from router import route_message
from session_manager import session_manager
from services.knowledge_service import KnowledgeService
import os, csv, pandas as pd

app = Flask(__name__)
app.secret_key = SECRET_KEY

kb = KnowledgeService()


@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════
# 核心聊天接口 — 所有消息经 Router 分发
# ═══════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "请提供 message 字段"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "消息不能为空"}), 400

    client_history = data.get("history") or []
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    if client_ip == "127.0.0.1":
        client_ip = request.remote_addr or ""

    # 用 session ID 区分用户
    session_id = session.get("user_id", "")
    if not session_id:
        import uuid
        session_id = uuid.uuid4().hex[:12]
        session["user_id"] = session_id

    # Router 决策 → Handler 处理
    result = route_message(
        message=question,
        session_id=session_id,
        client_ip=client_ip,
        client_history=client_history,
    )

    # 保存对话日志
    try:
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "chat_log.csv")
        log_exists = os.path.exists(log_path)
        with open(log_path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if not log_exists:
                w.writerow(["时间", "用户问题", "AI回答", "来源", "模式"])
            w.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                question[:100],
                result.get("reply", "")[:100],
                result.get("source", ""),
                result.get("mode", ""),
            ])
    except:
        pass

    return jsonify(result)


# ═══════════════════════════════════════════════
# 管理后台（不变）
# ═══════════════════════════════════════════════
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
    from config import KB_FAQ_PATH, KB_POLICY_PATH
    faq_count = 0
    policy_count = 0
    try:
        faq_df = pd.read_csv(KB_FAQ_PATH, encoding="utf-8-sig")
        faq_count = len(faq_df)
    except:
        pass
    try:
        pol_df = pd.read_csv(KB_POLICY_PATH, encoding="utf-8-sig")
        policy_count = len(pol_df)
    except:
        pass

    tickets = []
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            tickets = list(reader)[-20:]
    except:
        pass

    logs = []
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "emergency.log")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            logs = f.readlines()[-20:]
    except:
        pass

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
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    try:
        tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        rows = []
        archived = 0
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                row.pop(None, None)
                if row.get("状态") == "已解决":
                    archived += 1
                else:
                    rows.append(row)
        with open(tickets_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return jsonify({"status": "ok", "message": f"已归档 {archived} 条已解决工单"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/tickets/resolve/<ticket_id>", methods=["POST"])
def admin_tickets_resolve(ticket_id):
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    try:
        tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        rows = []
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                row.pop(None, None)
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
    user_id = session.get("user_id", "")
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    my = []
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("用户标识") == user_id:
                    my.append(row)
    except:
        pass
    return render_template("my_tickets.html", tickets=my)


@app.route("/admin/tickets")
def admin_tickets():
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    tickets = []
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            tickets = list(csv.DictReader(f))
    except:
        pass
    return jsonify(tickets)


@app.route("/admin/chat-logs")
def admin_chat_logs():
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "chat_log.csv")
    logs = []
    try:
        with open(log_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                logs.append(row)
    except:
        pass
    return jsonify(logs[-50:])


@app.route("/admin/risk-trends")
def admin_risk_trends():
    if not _check_admin():
        return jsonify({"error": "未登录"}), 401
    from datetime import datetime, timedelta
    tickets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    trends = {}
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        trends[d] = {"high": 0, "medium": 0, "total": 0}
    try:
        with open(tickets_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                date = row.get("时间", "")[:10]
                if date in trends:
                    trends[date]["total"] += 1
                    if row.get("风险等级", "") in ("高危", "紧急"):
                        trends[date]["high"] += 1
                    else:
                        trends[date]["medium"] += 1
    except:
        pass
    return jsonify(list(trends.items()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=DEBUG, host="0.0.0.0", port=port)
