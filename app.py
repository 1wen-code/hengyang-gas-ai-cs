"""
衡阳燃气 AI 客服 — Router + Session Mode + Handler 架构
"""
from flask import Flask, render_template, request, jsonify, session, redirect
from config import SECRET_KEY, DEBUG
from router import route
from services.knowledge_service import KnowledgeService
import os, csv, pandas as pd, uuid

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

    result = route(question, sid, client_ip, client_history)

    # 写入日志
    try:
        from datetime import datetime
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "chat_log.csv")
        exists = os.path.exists(p)
        with open(p, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["时间", "用户问题", "AI回答", "模式"])
            w.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                question[:200],
                result.get("reply", "")[:200],
                result.get("mode", ""),
            ])
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

    tickets, logs = [], []
    tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    lp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "emergency.log")
    try:
        with open(tp, "r", encoding="utf-8-sig") as f:
            tickets = list(csv.DictReader(f))[-20:]
    except: pass
    try:
        with open(lp, "r", encoding="utf-8") as f:
            logs = f.readlines()[-20:]
    except: pass

    return render_template("admin.html", faq_count=fc, policy_count=pc, tickets=tickets, logs=logs)


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
        tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        rows = []
        with open(tp, "r", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            fn = r.fieldnames
            for row in r:
                row.pop(None, None)
                if row.get("状态") != "已解决":
                    rows.append(row)
        with open(tp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fn)
            w.writeheader(); w.writerows(rows)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/admin/tickets/resolve/<tid>", methods=["POST"])
def admin_tickets_resolve(tid):
    if not _admin(): return jsonify({"error": "未登录"}), 401
    try:
        tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
        rows = []
        with open(tp, "r", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            fn = r.fieldnames
            for row in r:
                row.pop(None, None)
                if row.get("工单ID") == tid:
                    row["状态"] = "已解决"
                rows.append(row)
        with open(tp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fn)
            w.writeheader(); w.writerows(rows)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/my-tickets")
def my_tickets():
    uid = session.get("user_id", "")
    tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    my = []
    try:
        with open(tp, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("用户标识") == uid:
                    my.append(row)
    except: pass
    return render_template("my_tickets.html", tickets=my)


@app.route("/admin/tickets")
def admin_tickets():
    tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    try:
        with open(tp, "r", encoding="utf-8-sig") as f:
            return jsonify(list(csv.DictReader(f)))
    except:
        return jsonify([])


@app.route("/admin/chat-logs")
def admin_chat_logs():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    lp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "chat_log.csv")
    try:
        with open(lp, "r", encoding="utf-8-sig") as f:
            return jsonify(list(csv.DictReader(f))[-50:])
    except:
        return jsonify([])


@app.route("/admin/risk-trends")
def admin_risk_trends():
    if not _admin(): return jsonify({"error": "未登录"}), 401
    from datetime import datetime, timedelta
    tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "tickets.csv")
    trends = {}
    for i in range(6, -1, -1):
        trends[(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")] = {"high": 0, "medium": 0, "total": 0}
    try:
        with open(tp, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                d = row.get("时间", "")[:10]
                if d in trends:
                    trends[d]["total"] += 1
                    if row.get("风险等级", "") in ("高危", "紧急"):
                        trends[d]["high"] += 1
                    else:
                        trends[d]["medium"] += 1
    except: pass
    return jsonify(list(trends.items()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=DEBUG, host="0.0.0.0", port=port)
