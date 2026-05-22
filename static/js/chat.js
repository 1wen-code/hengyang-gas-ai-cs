/**
 * 衡阳市天然气有限责任公司 AI 客服 — 前端聊天逻辑
 */
(function () {
    "use strict";

    // ── DOM ─────────────────────────────────────────
    const chatMessages = document.getElementById("chatMessages");
    const welcomeScreen = document.getElementById("welcomeScreen");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const newChatBtn = document.getElementById("newChatBtn");
    const toggleSidebar = document.getElementById("toggleSidebar");
    const sidebar = document.getElementById("sidebar");
    const historyList = document.getElementById("historyList");

    // ── 状态 ───────────────────────────────────────
    let isWaiting = false;
    let currentChatId = Date.now();
    let chatHistory = [];
    let conversations = {};

    // ── 来源标签映射 ───────────────────────────────
    const SOURCE_LABELS = {
        knowledge_base: "知识库",
        ai_rag: "AI (RAG)",
        ai: "AI",
        reject: "服务范围提示",
        transfer: "转人工",
        emergency: "紧急事件",
        greeting: "智能欢迎",
        identity: "身份介绍",
        guide: "业务引导",
        error: "系统错误",
    };

    // ── 风险警告横幅（二级黄色 / 三级红色）──────
    function showEmergencyBanner(riskLevel, riskCode, ticketId) {
        // 移除旧横幅
        var oldBanner = document.getElementById("emergencyBanner");
        if (oldBanner) { oldBanner.remove(); }

        var banner = document.createElement("div");
        banner.id = "emergencyBanner";

        // 三级红色 / 二级黄色
        var isHigh = (riskCode === 3);
        var bgColor = isHigh ? "#dc2626" : "#d97706";
        var icon = isHigh ? "⚠" : "⚡";
        var label = isHigh ? "高危紧急" : "疑似风险";
        var actionText = isHigh ? "系统已强制转人工" : "建议检查并联系人工";

        banner.style.cssText = "background:" + bgColor + ";color:#fff;padding:12px 16px;margin:0;font-size:14px;display:flex;align-items:center;gap:8px;" +
            (isHigh ? "animation:emergency-pulse 1.5s ease-in-out infinite;" : "");
        banner.innerHTML = '<span style="font-size:20px;">' + icon + '</span> <strong>检测到燃气安全风险 [' + (riskLevel || '警告') + ']</strong> — ' + actionText;
        if (ticketId) {
            banner.innerHTML += ' <span style="opacity:0.8;font-size:12px;">工单：' + ticketId + '</span>';
        }
        banner.innerHTML += '<button onclick="this.parentElement.remove()" style="margin-left:auto;background:none;border:none;color:#fff;cursor:pointer;font-size:18px;">✕</button>';

        var header = document.querySelector(".chat-header");
        if (header) {
            header.parentNode.insertBefore(banner, header.nextSibling);
        }
    }

    // ── 紧急脉冲动画 ──────────────────────────────
    var emStyle = document.createElement("style");
    emStyle.textContent = "@keyframes emergency-pulse{0%,100%{opacity:1}50%{opacity:0.7}}";
    document.head.appendChild(emStyle);

    // ── 初始化 ─────────────────────────────────────
    function init() {
        loadConversations();
        bindEvents();
        autoResizeInput();
    }

    function bindEvents() {
        sendBtn.addEventListener("click", function(e) {
            e.preventDefault();
            handleSend();
        });
        messageInput.addEventListener("keydown", handleKeydown);
        messageInput.addEventListener("input", function() { autoResizeInput(); });
        newChatBtn.addEventListener("click", startNewChat);
        toggleSidebar.addEventListener("click", function () {
            if (window.innerWidth <= 768) {
                // 手机端：滑出侧边栏
                sidebar.classList.toggle("mobile-open");
                toggleOverlay();
            } else {
                sidebar.classList.toggle("collapsed");
            }
        });
        document.querySelectorAll(".suggestion-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                sendMessage(btn.dataset.msg);
            });
        });
    }

    // ── 发送 ───────────────────────────────────────
    function handleSend() {
        if (isWaiting) return;
        var text = messageInput.value.trim();
        if (!text) return;
        sendMessage(text);
    }

    function handleKeydown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function sendMessage(text) {
        hideWelcome();
        isWaiting = true;
        messageInput.value = "";
        autoResizeInput();
        updateSendButton();

        appendMessage("user", text);
        var typingEl = appendTyping();

        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                history: chatHistory.slice(-6).map(function(m) {
                    return { role: m.role === "user" ? "user" : "assistant", content: m.content };
                }),
            }),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                removeTyping(typingEl);
                if (data.error) {
                    appendMessage("bot", "抱歉，系统出现错误：" + data.error, "error");
                } else {
                    // 风险事件：显示颜色警告横幅
                    if (data.source === "emergency" || data.source === "warning") {
                        showEmergencyBanner(data.risk_level, data.risk_code, data.ticket_id);
                    }
                    var msgDiv = appendMessage(
                        "bot",
                        data.reply,
                        data.source,
                        data.match_question,
                        data.category,
                        data.law_basis,
                        data.rag_count
                    );
                    // 快捷追问按钮
                    if (data.source) {
                        addQuickReplies(data.source, msgDiv);
                    }
                }
                saveMessage("user", text);
                saveMessage("bot", data.reply, data.source,
                    data.match_question, data.category);
                updateHistoryItem(text);
            })
            .catch(function () {
                removeTyping(typingEl);
                appendMessage("bot",
                    "网络连接异常，请稍后重试。紧急情况请拨打 24 小时客服热线 0734-8677777。",
                    "error");
            })
            .finally(function () {
                isWaiting = false;
                updateSendButton();
                scrollToBottom();
                // 手机端恢复焦点，确保后续输入能触发按钮更新
                setTimeout(function() {
                    messageInput.focus();
                    messageInput.dispatchEvent(new Event("input"));
                }, 100);
            });
    }

    // ── 消息渲染 ───────────────────────────────────
    function appendMessage(role, content, source, matchQuestion, category, lawBasis, ragCount) {
        var div = document.createElement("div");
        div.className = "message " + role;
        if (source === "transfer" || source === "error" || source === "reject") {
            div.classList.add(source);
        }

        // 头像
        var avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "user" ? "我" : "衡";

        // 消息体
        var body = document.createElement("div");
        body.className = "message-body";

        var msgContent = document.createElement("div");
        msgContent.className = "message-content";
        msgContent.innerHTML = renderContent(content);
        body.appendChild(msgContent);

        // 元数据
        if (source && role === "bot") {
            var meta = document.createElement("div");
            meta.className = "message-meta";

            var label = SOURCE_LABELS[source] || source;

            var tag = document.createElement("span");
            tag.className = "source-tag " + source;
            tag.textContent = label;
            meta.appendChild(tag);

            if (ragCount && ragCount > 0) {
                var ragSpan = document.createElement("span");
                ragSpan.textContent = "上下文：" + ragCount + " 条";
                meta.appendChild(ragSpan);
            }
            if (matchQuestion) {
                var matchSpan = document.createElement("span");
                matchSpan.textContent = "匹配：" + matchQuestion;
                meta.appendChild(matchSpan);
            }
            if (category) {
                var catSpan = document.createElement("span");
                catSpan.textContent = "分类：" + category;
                meta.appendChild(catSpan);
            }
            if (lawBasis) {
                var lawSpan = document.createElement("span");
                lawSpan.style.color = "var(--text-muted)";
                lawSpan.textContent = "依据：" + lawBasis;
                meta.appendChild(lawSpan);
            }

            body.appendChild(meta);
        }

        div.appendChild(avatar);
        div.appendChild(body);
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function appendTyping() {
        var div = document.createElement("div");
        div.className = "message bot";

        var avatar = document.createElement("div");
        avatar.className = "message-avatar bot-avatar";
        avatar.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>';

        var body = document.createElement("div");
        body.className = "message-body";
        body.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

        div.appendChild(avatar);
        div.appendChild(body);
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function removeTyping(el) {
        if (el && el.parentNode) {
            el.parentNode.removeChild(el);
        }
    }

    // ── 简单 Markdown ──────────────────────────────
    function renderContent(text) {
        if (!text) return "";
        var html = escapeHtml(text);
        html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\n\n/g, "<br><br>");
        html = html.replace(/\n/g, "<br>");
        return html;
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // ── 欢迎页 ─────────────────────────────────────
    function hideWelcome() {
        if (welcomeScreen && welcomeScreen.parentNode) {
            welcomeScreen.style.display = "none";
        }
    }

    function showWelcome() {
        if (welcomeScreen) {
            welcomeScreen.style.display = "";
        }
    }

    // ── 输入框 ─────────────────────────────────────
    function autoResizeInput() {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + "px";
    }

    function updateSendButton() {
        if (isWaiting) {
            sendBtn.classList.add("sending");
        } else {
            sendBtn.classList.remove("sending");
        }
    }

    // ── 滚动 ───────────────────────────────────────
    function scrollToBottom() {
        requestAnimationFrame(function () {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // ── 对话持久化 ─────────────────────────────────
    function saveMessage(role, content, source, matchQuestion, category) {
        chatHistory.push({
            role: role, content: content, source: source,
            matchQuestion: matchQuestion, category: category, time: Date.now()
        });
        conversations[currentChatId] = conversations[currentChatId] || { title: "", messages: [] };
        conversations[currentChatId].messages = chatHistory;
        if (!conversations[currentChatId].title && role === "user") {
            conversations[currentChatId].title = content.slice(0, 20);
        }
        persistConversations();
    }

    function persistConversations() {
        try {
            localStorage.setItem("hengyang_gas_chats", JSON.stringify(conversations));
        } catch (e) { /* quota exceeded */ }
    }

    function loadConversations() {
        try {
            var raw = localStorage.getItem("hengyang_gas_chats");
            if (raw) { conversations = JSON.parse(raw); }
        } catch (e) {
            conversations = {};
        }
        renderHistoryList();
    }

    // ── 历史列表 ───────────────────────────────────
    function renderHistoryList() {
        historyList.innerHTML = "";
        var ids = Object.keys(conversations).sort(function (a, b) { return b - a; });
        ids.forEach(function (id) {
            var conv = conversations[id];
            var item = document.createElement("div");
            item.className = "history-item" + (Number(id) === currentChatId ? " active" : "");
            item.textContent = conv.title || "新对话";
            item.addEventListener("click", function () { loadChat(Number(id)); });
            historyList.appendChild(item);
        });
    }

    function updateHistoryItem(firstMsg) {
        conversations[currentChatId].title = firstMsg.slice(0, 20);
        persistConversations();
        renderHistoryList();
    }

    function loadChat(id) {
        if (isWaiting) return;
        currentChatId = id;
        chatHistory = conversations[id].messages || [];
        while (chatMessages.children.length > 0) {
            chatMessages.removeChild(chatMessages.firstChild);
        }
        if (chatHistory.length === 0) {
            showWelcome();
        } else {
            hideWelcome();
            chatHistory.forEach(function (msg) {
                appendMessage(msg.role, msg.content, msg.source,
                    msg.matchQuestion, msg.category);
            });
        }
        renderHistoryList();
        scrollToBottom();
    }

    function startNewChat() {
        if (isWaiting) return;
        currentChatId = Date.now();
        chatHistory = [];
        while (chatMessages.children.length > 0) {
            chatMessages.removeChild(chatMessages.firstChild);
        }
        var welcomeDiv = document.createElement("div");
        welcomeDiv.className = "welcome-screen";
        welcomeDiv.id = "welcomeScreen";
        welcomeDiv.innerHTML = welcomeScreen.innerHTML;
        chatMessages.appendChild(welcomeDiv);
        chatMessages.querySelectorAll(".suggestion-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                sendMessage(btn.dataset.msg);
            });
        });
        conversations[currentChatId] = { title: "", messages: [] };
        persistConversations();
        renderHistoryList();
        messageInput.focus();
    }

    // ═══════════════════════════════════════════════
    // 打字机效果
    // ═══════════════════════════════════════════════
    function typewriter(el, html, speed, callback) {
        // Strip HTML for typing, then apply at end
        var temp = document.createElement("div");
        temp.innerHTML = html;
        var text = temp.textContent || temp.innerText || "";
        var i = 0;
        el.textContent = "";
        function type() {
            if (i < text.length) {
                el.textContent += text.charAt(i);
                i++;
                scrollToBottom();
                setTimeout(type, speed || 20);
            } else {
                el.innerHTML = html; // Apply real HTML at end
                if (callback) callback();
            }
        }
        type();
    }

    // ═══════════════════════════════════════════════
    // 快捷追问按钮
    // ═══════════════════════════════════════════════
    var QUICK_REPLIES = {
        greeting: ['燃气开户', '燃气缴费', '收费标准', '燃气泄漏怎么办'],
        identity: ['如何开户', '怎么缴费', '燃气报修', '安全检查'],
        guide: ['居民开户', '商业开户', '燃气过户', '故障报修'],
        faq: ['需要什么材料', '多少钱', '多久能办好', '转人工'],
        transfer: ['如何开户', '燃气缴费', '收费标准'],
        default: ['如何办理开户', '怎么缴纳燃气费', '燃气泄漏怎么办', '转人工客服'],
    };

    function addQuickReplies(source, msgDiv) {
        // Remove old quick replies
        var old = document.querySelectorAll(".quick-replies");
        old.forEach(function(el) { el.remove(); });

        var replies = QUICK_REPLIES[source] || QUICK_REPLIES["default"];
        var container = document.createElement("div");
        container.className = "quick-replies";
        container.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;padding:8px 40px 8px 86px;";

        replies.forEach(function(r) {
            var btn = document.createElement("button");
            btn.textContent = r;
            btn.style.cssText = "padding:6px 14px;border:1px solid var(--border-color);border-radius:16px;background:transparent;color:var(--text-secondary);font-size:12px;cursor:pointer;transition:all 0.15s;";
            btn.onmouseover = function() { this.style.background = "var(--bg-bot-msg)"; this.style.color = "var(--text-primary)"; };
            btn.onmouseout = function() { this.style.background = "transparent"; this.style.color = "var(--text-secondary)"; };
            btn.onclick = function() { sendMessage(r); };
            container.appendChild(btn);
        });
        msgDiv.parentNode.insertBefore(container, msgDiv.nextSibling);
    }

    // ═══════════════════════════════════════════════
    // 语音输入 — 高级玻璃按钮（功能预留）
    // ═══════════════════════════════════════════════
    var voiceBtn = null;

    function addVoiceButton() {
        if (voiceBtn) return;

        voiceBtn = document.createElement("button");
        voiceBtn.id = "voiceBtn";
        voiceBtn.title = "语音输入";
        voiceBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line></svg>';

        voiceBtn.addEventListener("click", function(e) {
            e.preventDefault();
            e.stopPropagation();
            showVoiceToast();
        });

        var inputWrapper = document.querySelector(".input-wrapper");
        if (inputWrapper) {
            inputWrapper.insertBefore(voiceBtn, inputWrapper.firstChild);
        }
    }

    function showVoiceToast() {
        var old = document.querySelector(".voice-toast");
        if (old) old.remove();

        var toast = document.createElement("div");
        toast.className = "voice-toast";
        toast.innerHTML = '<span style="font-size:18px;margin-right:6px;">🎤</span> 语音功能即将上线，当前版本请使用文字输入';
        toast.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(22,33,62,0.95);color:#fff;padding:14px 24px;border-radius:30px;font-size:14px;z-index:9999;white-space:nowrap;border:1px solid rgba(255,255,255,0.1);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 8px 32px rgba(0,0,0,0.4);animation:voice-toast-in 0.3s ease,voice-toast-out 0.3s ease 2.5s forwards;";
        document.body.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 3000);
    }

    // ═══════════════════════════════════════════════
    // 主题切换
    // ═══════════════════════════════════════════════
    var isDark = true;
    var themeBtn = null;
    function addThemeButton() {
        if (themeBtn) return;
        themeBtn = document.createElement("button");
        themeBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path></svg>';
        themeBtn.title = "切换主题";
        themeBtn.style.cssText = "background:transparent;border:none;color:var(--text-secondary);cursor:pointer;padding:6px;border-radius:6px;";
        themeBtn.onclick = toggleTheme;
        var header = document.querySelector(".chat-header");
        if (header) {
            header.appendChild(themeBtn);
        }
    }

    function toggleTheme() {
        isDark = !isDark;
        var root = document.documentElement;
        if (isDark) {
            root.style.setProperty("--bg-primary", "#343541");
            root.style.setProperty("--bg-secondary", "#202123");
            root.style.setProperty("--bg-input", "#40414f");
            root.style.setProperty("--bg-user-msg", "#343541");
            root.style.setProperty("--bg-bot-msg", "#444654");
            root.style.setProperty("--text-primary", "#ececf1");
            root.style.setProperty("--text-secondary", "#c5c5d2");
            root.style.setProperty("--text-muted", "#8e8ea0");
        } else {
            root.style.setProperty("--bg-primary", "#ffffff");
            root.style.setProperty("--bg-secondary", "#f7f7f8");
            root.style.setProperty("--bg-input", "#f0f0f0");
            root.style.setProperty("--bg-user-msg", "#ffffff");
            root.style.setProperty("--bg-bot-msg", "#f7f7f8");
            root.style.setProperty("--text-primary", "#1a1a1a");
            root.style.setProperty("--text-secondary", "#555");
            root.style.setProperty("--text-muted", "#999");
        }
    }

    // ═══════════════════════════════════════════════
    // 导出聊天记录
    // ═══════════════════════════════════════════════
    function addExportButton() {
        var btn = document.createElement("button");
        btn.textContent = "导出";
        btn.title = "导出聊天记录";
        btn.style.cssText = "background:transparent;border:1px solid var(--border-color);color:var(--text-secondary);cursor:pointer;padding:4px 10px;border-radius:4px;font-size:11px;margin-right:4px;";
        btn.onclick = exportChat;
        var header = document.querySelector(".chat-header");
        if (header) {
            header.appendChild(btn);
        }
    }

    function exportChat() {
        var lines = [];
        lines.push("衡阳市天然气AI客服 - 聊天记录");
        lines.push("导出时间: " + new Date().toLocaleString());
        lines.push("=".repeat(50));
        chatHistory.forEach(function(m) {
            var role = m.role === "user" ? "用户" : "客服";
            lines.push("");
            lines.push("【" + role + "】 " + new Date(m.time).toLocaleTimeString());
            lines.push(m.content);
        });
        var text = lines.join("\n");
        var blob = new Blob([text], {type: "text/plain;charset=utf-8"});
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "燃气客服聊天记录_" + new Date().toISOString().slice(0,10) + ".txt";
        a.click();
        URL.revokeObjectURL(url);
    }

    // ═══════════════════════════════════════════════
    // 演示路径按钮
    // ═══════════════════════════════════════════════
    function addDemoButton() {
        var btn = document.createElement("button");
        btn.textContent = "演示";
        btn.title = "自动演示";
        btn.style.cssText = "background:var(--accent);border:none;color:#fff;cursor:pointer;padding:4px 10px;border-radius:4px;font-size:11px;margin-right:4px;";
        btn.onclick = runDemo;
        var header = document.querySelector(".chat-header");
        if (header) {
            header.appendChild(btn);
        }
    }

    var demoSteps = [
        "你好",
        "我要开户",
        "需要什么材料",
        "怎么交燃气费",
        "燃气泄漏怎么办",
    ];
    function runDemo() {
        var i = 0;
        function next() {
            if (i < demoSteps.length) {
                sendMessage(demoSteps[i]);
                i++;
                setTimeout(next, 3000);
            }
        }
        next();
    }

    // ── 启动扩展功能 ──────────────────────────────
    function initExtensions() {
        addVoiceButton();
        addThemeButton();
        addExportButton();
        addDemoButton();
    }
    setTimeout(initExtensions, 500);

    // ── 手机侧边栏遮罩 ────────────────────────────
    var overlay = null;
    function getOverlay() {
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "sidebar-overlay";
            overlay.addEventListener("click", function() {
                sidebar.classList.remove("mobile-open");
                overlay.classList.remove("show");
            });
            document.body.appendChild(overlay);
        }
        return overlay;
    }
    function toggleOverlay() {
        var ol = getOverlay();
        if (sidebar.classList.contains("mobile-open")) {
            ol.classList.add("show");
        } else {
            ol.classList.remove("show");
        }
    }

    // ── 启动 ───────────────────────────────────────
    init();
})();
