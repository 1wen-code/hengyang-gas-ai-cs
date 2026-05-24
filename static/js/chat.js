/**
 * 衡阳市天然气有限责任公司 AI 客服 — 企业级前端交互逻辑
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
    let thinkingInterval = null;

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
        crisis: "心理安抚",
        emotion: "情绪安抚",
        complaint: "投诉受理",
        error: "系统错误",
        warning: "风险提醒",
    };

    // ── 来源→分类映射 ───────────────────────────────
    const SOURCE_CATEGORY = {
        emergency: "cat-emergency",
        warning: "cat-emergency",
        guide: "cat-guide",
        knowledge_base: "cat-other",
        ai_rag: "cat-other",
        greeting: "cat-guide",
        transfer: "cat-other",
    };

    // ── AI思考状态文字 ──────────────────────────────
    const THINKING_STATES = [
        "正在分析问题...",
        "正在检索知识库...",
        "正在匹配燃气法规...",
    ];

    // ── 风险警告横幅 ───────────────────────────────
    function showEmergencyBanner(riskLevel, riskCode, ticketId) {
        const oldBanner = document.getElementById("emergencyBanner");
        if (oldBanner) oldBanner.remove();

        const banner = document.createElement("div");
        banner.id = "emergencyBanner";

        const isHigh = (riskCode === 3);
        banner.className = "risk-banner" + (isHigh ? "" : " warning");

        const icon = isHigh ? "⚠️" : "⚡";
        const label = isHigh ? "检测到燃气安全高风险" : "检测到疑似风险";
        const actionText = isHigh ? "系统已自动生成工单并转人工" : "建议检查并联系人工";

        let html = '<span class="risk-icon">' + icon + '</span>';
        html += '<strong>' + label + '</strong> — ' + actionText;
        if (ticketId) {
            html += ' <span style="opacity:0.8;font-size:11px;">工单：' + ticketId + '</span>';
        }
        html += '<button class="risk-close" onclick="this.parentElement.remove()">✕</button>';
        banner.innerHTML = html;

        const header = document.querySelector(".chat-header");
        if (header) {
            header.parentNode.insertBefore(banner, header.nextSibling);
        }
    }

    // ── 初始化 ─────────────────────────────────────
    function init() {
        loadTheme();
        loadConversations();
        bindEvents();
        autoResizeInput();
        updateSystemStats();
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
                sidebar.classList.toggle("mobile-open");
                toggleOverlay();
            } else {
                sidebar.classList.toggle("collapsed");
            }
        });
        // 快捷入口卡片
        document.querySelectorAll(".suggestion-btn, .quick-entry-card").forEach(function (btn) {
            btn.addEventListener("click", function () {
                sendMessage(btn.dataset.msg);
            });
        });
    }

    // ── 发送 ───────────────────────────────────────
    function handleSend() {
        if (isWaiting) return;
        const text = messageInput.value.trim();
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
        const typingEl = appendTyping();

        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                history: chatHistory.slice(-10).map(function(m) {
                    return { role: m.role === "user" ? "user" : "assistant", content: m.content };
                }),
            }),
            signal: AbortSignal.timeout(25000),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                removeTyping(typingEl);
                if (data.error) {
                    appendMessage("bot", "抱歉，系统出现错误：" + data.error, "error");
                } else {
                    // 风险事件
                    const riskLevel = (data.risk && data.risk.level >= 2) ? data.risk.level : null;
                    const isRisk = riskLevel || data.source === "emergency" || data.source === "warning";
                    if (isRisk) {
                        const riskLabel = (data.risk && data.risk.label) || data.risk_level || "警告";
                        const riskCode = riskLevel || data.risk_code || 2;
                        const ticketId = data.ticket || data.ticket_id || null;
                        showEmergencyBanner(riskLabel, riskCode, ticketId);
                    } else {
                        // 非风险消息：隐藏旧 banner
                        const oldBanner = document.getElementById("emergencyBanner");
                        if (oldBanner) oldBanner.remove();
                    }

                    // 构建消息 class
                    let extraClass = "";
                    if (data.source === "emergency" || data.source === "warning" || (data.risk && data.risk.level >= 2)) {
                        extraClass = "risk-high";
                    }

                    const msgDiv = appendMessage(
                        "bot", data.reply, data.source,
                        data.match_question, data.category,
                        data.law_basis, data.rag_count, extraClass
                    );

                    if (data.source) {
                        addQuickReplies(data.source, msgDiv);
                    }

                }
                saveMessage("user", text);
                saveMessage("bot", data.reply, data.source,
                    data.match_question, data.category);
                updateHistoryItem(text);
                updateSystemStats();
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
                setTimeout(function() {
                    messageInput.focus();
                    messageInput.dispatchEvent(new Event("input"));
                }, 100);
            });
    }

    // ── 消息渲染 ───────────────────────────────────
    function appendMessage(role, content, source, matchQuestion, category, lawBasis, ragCount, extraClass) {
        const div = document.createElement("div");
        div.className = "message " + role;
        if (source === "transfer" || source === "error" || source === "reject") {
            div.classList.add(source);
        }
        if (extraClass) {
            div.classList.add(extraClass);
        }

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "user" ? "我" : "衡";

        const body = document.createElement("div");
        body.className = "message-body";

        const msgContent = document.createElement("div");
        msgContent.className = "message-content";
        msgContent.innerHTML = renderContent(content);
        body.appendChild(msgContent);

        // 元数据：只显示用户可理解的标签，不显示 handler 内部名
        if (source && role === "bot" && SOURCE_LABELS[source]) {
            const meta = document.createElement("div");
            meta.className = "message-meta";

            const label = SOURCE_LABELS[source];
            const tag = document.createElement("span");
            tag.className = "source-tag " + source;
            tag.textContent = label;
            meta.appendChild(tag);
            body.appendChild(meta);
        }

        div.appendChild(avatar);
        div.appendChild(body);
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function appendTyping() {
        const div = document.createElement("div");
        div.className = "message bot";

        const avatar = document.createElement("div");
        avatar.className = "message-avatar bot-avatar";
        avatar.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>';

        const body = document.createElement("div");
        body.className = "message-body";

        const indicator = document.createElement("div");
        indicator.className = "typing-indicator";

        const dots = document.createElement("div");
        dots.className = "typing-dots";
        dots.innerHTML = "<span></span><span></span><span></span>";
        indicator.appendChild(dots);

        const thinkText = document.createElement("span");
        thinkText.className = "thinking-text";
        thinkText.textContent = THINKING_STATES[0];
        indicator.appendChild(thinkText);

        body.appendChild(indicator);
        div.appendChild(avatar);
        div.appendChild(body);
        chatMessages.appendChild(div);

        // 循环切换思考文字
        let idx = 0;
        thinkingInterval = setInterval(function() {
            idx = (idx + 1) % THINKING_STATES.length;
            thinkText.textContent = THINKING_STATES[idx];
        }, 1800);

        // 存储interval到元素上以便清理
        div._thinkingInterval = thinkingInterval;

        scrollToBottom();
        return div;
    }

    function removeTyping(el) {
        if (el && el._thinkingInterval) {
            clearInterval(el._thinkingInterval);
        }
        if (el && el.parentNode) {
            el.parentNode.removeChild(el);
        }
    }

    // ── 简单 Markdown ──────────────────────────────
    function renderContent(text) {
        if (!text) return "";
        let html = escapeHtml(text);
        html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\n\n/g, "<br><br>");
        html = html.replace(/\n/g, "<br>");
        return html;
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
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
            const raw = localStorage.getItem("hengyang_gas_chats");
            if (raw) { conversations = JSON.parse(raw); }
        } catch (e) {
            conversations = {};
        }
        renderHistoryList();
    }

    // ── 相对时间 ───────────────────────────────────
    function relativeTime(ts) {
        const diff = Date.now() - ts;
        const sec = Math.floor(diff / 1000);
        if (sec < 60) return "刚刚";
        const min = Math.floor(sec / 60);
        if (min < 60) return min + "分钟前";
        const hr = Math.floor(min / 60);
        if (hr < 24) return hr + "小时前";
        const d = new Date(ts);
        if (hr < 48) return "昨天";
        return (d.getMonth() + 1) + "/" + d.getDate();
    }

    // ── 历史列表 ───────────────────────────────────
    function renderHistoryList() {
        historyList.innerHTML = "";
        const ids = Object.keys(conversations).sort(function (a, b) { return b - a; });

        if (ids.length === 0) {
            const empty = document.createElement("div");
            empty.className = "sidebar-history-empty";
            empty.textContent = "暂无历史对话";
            historyList.appendChild(empty);
            return;
        }

        ids.forEach(function (id) {
            const conv = conversations[id];
            const item = document.createElement("div");
            item.className = "history-item" + (Number(id) === currentChatId ? " active" : "");

            // 推测分类
            let catClass = "cat-other";
            let catLabel = "";
            if (conv.messages && conv.messages.length > 0) {
                for (let i = 0; i < conv.messages.length; i++) {
                    const s = conv.messages[i].source;
                    if (s === "emergency") { catClass = "cat-emergency"; catLabel = "高危"; break; }
                    if (s === "warning") { catClass = "cat-emergency"; catLabel = "风险"; break; }
                    if (s === "guide") { catClass = "cat-guide"; catLabel = "业务"; break; }
                    if (s === "greeting") { catClass = "cat-guide"; catLabel = "咨询"; break; }
                }
            }

            // 找到最早用户消息时间
            let msgTime = "";
            if (conv.messages && conv.messages.length > 0) {
                for (let i = 0; i < conv.messages.length; i++) {
                    if (conv.messages[i].time) { msgTime = relativeTime(conv.messages[i].time); break; }
                }
            }

            const titleSpan = document.createElement("span");
            titleSpan.className = "history-item-title";
            titleSpan.textContent = conv.title || "新对话";

            const metaDiv = document.createElement("div");
            metaDiv.className = "history-item-meta";

            if (catLabel) {
                const catSpan = document.createElement("span");
                catSpan.className = "history-category " + catClass;
                catSpan.textContent = catLabel;
                metaDiv.appendChild(catSpan);
            }

            const timeSpan = document.createElement("span");
            timeSpan.className = "history-time";
            timeSpan.textContent = msgTime;
            metaDiv.appendChild(timeSpan);

            item.appendChild(titleSpan);
            item.appendChild(metaDiv);
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
        updateSystemStats();
    }

    function startNewChat() {
        if (isWaiting) return;
        currentChatId = Date.now();
        chatHistory = [];
        const oldBanner = document.getElementById("emergencyBanner");
        if (oldBanner) oldBanner.remove();

        while (chatMessages.children.length > 0) {
            chatMessages.removeChild(chatMessages.firstChild);
        }

        // 重建欢迎页
        const welcomeDiv = document.createElement("div");
        welcomeDiv.className = "welcome-screen";
        welcomeDiv.id = "welcomeScreen";
        // 从原始HTML克隆欢迎内容
        const origWelcome = document.querySelector(".welcome-screen");
        if (origWelcome) {
            welcomeDiv.innerHTML = origWelcome.innerHTML;
        }
        chatMessages.appendChild(welcomeDiv);

        // 重新绑定快捷入口
        document.querySelectorAll(".suggestion-btn, .quick-entry-card").forEach(function (btn) {
            btn.addEventListener("click", function () {
                sendMessage(btn.dataset.msg);
            });
        });

        conversations[currentChatId] = { title: "", messages: [] };
        persistConversations();
        renderHistoryList();
        updateSystemStats();
        messageInput.focus();
    }

    // ── 系统运行状态 ───────────────────────────────
    function updateSystemStats() {
        const statConsult = document.getElementById("statConsult");
        const statRisk = document.getElementById("statRisk");
        const statQueue = document.getElementById("statQueue");

        if (!statConsult) return;

        // 统计今日咨询
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayMs = today.getTime();
        let todayCount = 0;
        let riskCount = 0;

        Object.keys(conversations).forEach(function(id) {
            const conv = conversations[id];
            if (conv.messages) {
                conv.messages.forEach(function(m) {
                    if (m.time && m.time >= todayMs && m.role === "user") {
                        todayCount++;
                    }
                    if (m.time && m.time >= todayMs && (m.source === "emergency" || m.source === "warning")) {
                        riskCount++;
                    }
                });
            }
        });

        statConsult.textContent = todayCount || "--";
        statRisk.textContent = riskCount || "--";

        // 人工排队（模拟）
        if (statQueue) {
            const hr = new Date().getHours();
            const queue = (hr >= 9 && hr <= 18) ? Math.floor(Math.random() * 5) + 1 : 0;
            statQueue.textContent = queue > 0 ? queue + "人" : "0人";
        }
    }

    // ═══════════════════════════════════════════════
    // 快捷追问按钮
    // ═══════════════════════════════════════════════
    const QUICK_REPLIES = {
        greeting: ['燃气开户', '燃气缴费', '收费标准', '燃气泄漏怎么办'],
        identity: ['如何开户', '怎么缴费', '燃气报修', '安全检查'],
        guide: ['居民开户', '商业开户', '燃气过户', '故障报修'],
        faq: ['需要什么材料', '多少钱', '多久能办好'],
        transfer: ['如何开户', '燃气缴费', '收费标准'],
        default: ['如何办理开户', '怎么缴纳燃气费', '燃气泄漏怎么办'],
    };

    function addQuickReplies(source, msgDiv) {
        const old = document.querySelectorAll(".quick-replies");
        old.forEach(function(el) { el.remove(); });

        const replies = QUICK_REPLIES[source] || QUICK_REPLIES["default"];
        const container = document.createElement("div");
        container.className = "quick-replies";

        replies.forEach(function(r) {
            const btn = document.createElement("button");
            btn.className = "quick-reply-btn";
            btn.textContent = r;
            btn.addEventListener("click", function() { sendMessage(r); });
            container.appendChild(btn);
        });
        msgDiv.parentNode.insertBefore(container, msgDiv.nextSibling);
    }

    // ═══════════════════════════════════════════════
    // 语音输入 — 玻璃按钮（功能预留）
    // ═══════════════════════════════════════════════
    let voiceBtn = null;

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

        const inputWrapper = document.querySelector(".input-wrapper");
        if (inputWrapper) {
            inputWrapper.insertBefore(voiceBtn, inputWrapper.firstChild);
        }
    }

    function showVoiceToast() {
        const old = document.querySelector(".voice-toast");
        if (old) old.remove();

        const toast = document.createElement("div");
        toast.className = "voice-toast";
        toast.textContent = "语音功能即将上线，请使用文字输入";
        document.body.appendChild(toast);
        setTimeout(function() {
            toast.style.animation = "voice-toast-out 0.3s ease forwards";
            setTimeout(function() { toast.remove(); }, 300);
        }, 2500);
    }

    // ═══════════════════════════════════════════════
    // 主题切换 (data-theme)
    // ═══════════════════════════════════════════════
    let isDark = true;
    let themeBtn = null;

    function loadTheme() {
        try {
            const saved = localStorage.getItem("hengyang_theme");
            if (saved === "light") {
                isDark = false;
                document.documentElement.setAttribute("data-theme", "light");
            }
        } catch(e) {}
    }

    function addThemeButton() {
        if (themeBtn) return;
        themeBtn = document.createElement("button");
        themeBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path></svg>';
        themeBtn.title = "切换主题";
        themeBtn.style.cssText = "background:transparent;border:none;color:var(--text-secondary);cursor:pointer;padding:6px;border-radius:6px;display:flex;align-items:center;";
        themeBtn.addEventListener("click", toggleTheme);
        const header = document.querySelector(".chat-header");
        if (header) {
            header.appendChild(themeBtn);
        }
    }

    function toggleTheme() {
        isDark = !isDark;
        document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
        try {
            localStorage.setItem("hengyang_theme", isDark ? "dark" : "light");
        } catch(e) {}
    }

    // ═══════════════════════════════════════════════
    // 导出聊天记录
    // ═══════════════════════════════════════════════
    function addExportButton() {
        const btn = document.createElement("button");
        btn.textContent = "导出";
        btn.title = "导出聊天记录";
        btn.style.cssText = "background:transparent;border:1px solid var(--border-color);color:var(--text-secondary);cursor:pointer;padding:4px 10px;border-radius:var(--radius-xs);font-size:11px;margin-right:4px;";
        btn.addEventListener("click", exportChat);
        const header = document.querySelector(".chat-header");
        if (header) header.appendChild(btn);
    }

    function exportChat() {
        const lines = [];
        lines.push("衡阳市天然气AI客服 - 聊天记录");
        lines.push("导出时间: " + new Date().toLocaleString());
        lines.push("=".repeat(50));
        chatHistory.forEach(function(m) {
            const role = m.role === "user" ? "用户" : "客服";
            lines.push("");
            lines.push("【" + role + "】 " + new Date(m.time).toLocaleTimeString());
            lines.push(m.content);
        });
        const text = lines.join("\n");
        const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "燃气客服聊天记录_" + new Date().toISOString().slice(0, 10) + ".txt";
        a.click();
        URL.revokeObjectURL(url);
    }

    // ═══════════════════════════════════════════════
    // 演示路径
    // ═══════════════════════════════════════════════
    function addDemoButton() {
        const btn = document.createElement("button");
        btn.textContent = "演示";
        btn.title = "自动演示";
        btn.style.cssText = "background:var(--accent);border:none;color:#fff;cursor:pointer;padding:4px 10px;border-radius:var(--radius-xs);font-size:11px;margin-right:4px;";
        btn.addEventListener("click", runDemo);
        const header = document.querySelector(".chat-header");
        if (header) header.appendChild(btn);
    }

    const demoSteps = [
        "你好", "我要开户", "需要什么材料", "怎么交燃气费", "燃气泄漏怎么办",
    ];

    function runDemo() {
        let i = 0;
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
    let overlay = null;
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
        const ol = getOverlay();
        if (sidebar.classList.contains("mobile-open")) {
            ol.classList.add("show");
        } else {
            ol.classList.remove("show");
        }
    }

    // ── 启动 ───────────────────────────────────────
    init();
})();
