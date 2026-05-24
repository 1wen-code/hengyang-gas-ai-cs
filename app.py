"""
衡阳燃气 AI 客服 — Router + Session Mode + Handler 架构
"""
from flask import Flask, render_template, request, jsonify, session, redirect
from config import SECRET_KEY, DEBUG
from router import route
from services.knowledge_service import KnowledgeService
from db import (
    add_chat, get_chat_logs, get_tickets, get_user_tickets,
    resolve_ticket, archive_resolved, ticket_count,
    get_emergency_logs, emergency_log_count, get_risk_trends,
)
import os, pandas as pd, uuid

app = Flask(__name__)
app.secret_key = SECRET_KEY

kb = KnowledgeService()


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

    client_history = data.get("history") or []
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    if client_ip == "127.0.0.1":
        client_ip = request.remote_addr or ""

    sid = session.get("user_id", "")
    if not sid:
        sid = uuid.uuid4().hex[:12]
        session["user_id"] = sid
    from session_manager import sessions
    sessions.get(sid)["user_id"] = sid

    result = route(question, sid, client_ip, client_history)

    # 写入 SQLite
    try:
        add_chat(question, result.get("reply", ""), result.get("mode", ""))
    except:
        pass

    return jsonify(result)


# ═══════════════════════════════════════════════
# 管理后台
# ═══════════════════════════════════════════════
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "hygas0826")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        return render_template("admin_login.html", error="密码错误")
    return render_template("admin_login.html", error="")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")


def _admin():
    return session.get("admin", False)


@app.route("/admin")
def admin():
    if not _admin():
        return redirect("/admin/login")
    from config import KB_FAQ_PATH, KB_POLICY_PATH
    fc = pc = 0
    try:
        fc = len(pd.read_csv(KB_FAQ_PATH, encoding="utf-8-sig"))
    except: pass
    try:
        pc = len(pd.read_csv(KB_POLICY_PATH, encoding="utf-8-sig"))
    except: pass

    return render_template("admin.html",
        faq_count=fc, policy_count=pc,
        tickets=get_tickets(20),
        logs=get_emergency_logs(20),
        ticket_count=ticket_count(),
        log_count=emergency_log_count(),
    )


@app.route("/admin/reload", methods=["POST"])
def admin_reload():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        kb.reload()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    from config import KB_FAQ_PATH
    f = request.files.get("file")
    if not f or not f.filename.endswith((".xlsx", ".csv")):
        return jsonify({"status": "error", "message": "请上传.xlsx或.csv文件"}), 400
    f.save(KB_FAQ_PATH if f.filename.endswith(".csv") else KB_FAQ_PATH.replace(".csv", ".xlsx"))
    try:
        kb.reload()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/tickets/clear", methods=["POST"])
def admin_tickets_clear():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        archive_resolved()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/tickets/resolve/<tid>", methods=["POST"])
def admin_tickets_resolve(tid):
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        resolve_ticket(tid)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/my-tickets")
def my_tickets():
    uid = session.get("user_id", "")
    return render_template("my_tickets.html", tickets=get_user_tickets(uid))


@app.route("/admin/tickets")
def admin_tickets():
    try:
        return jsonify(get_tickets(50))
    except:
        return jsonify([])


@app.route("/admin/chat-logs")
def admin_chat_logs():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        return jsonify(get_chat_logs(50))
    except:
        return jsonify([])


@app.route("/admin/risk-trends")
def admin_risk_trends():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        return jsonify(get_risk_trends(7))
    except:
        return jsonify([])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=DEBUG, host="0.0.0.0", port=port)
