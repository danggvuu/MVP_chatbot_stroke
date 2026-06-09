document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");
    const modelBadge = document.getElementById("model-badge");
    const emergencyBanner = document.getElementById("emergency-banner");
    const closeBannerBtn = document.getElementById("close-banner-btn");
    
    // Tab Elements
    const tabActiveSources = document.getElementById("tab-active-sources");
    const tabAllSources = document.getElementById("tab-all-sources");
    const paneActiveSources = document.getElementById("pane-active-sources");
    const paneAllSources = document.getElementById("pane-all-sources");
    const activeSourcesEmpty = document.getElementById("active-sources-empty");
    const activeSourcesList = document.getElementById("active-sources-list");
    const allSourcesList = document.getElementById("all-sources-list");
    const totalChunksCount = document.getElementById("total-chunks-count");
    
    // Suggested Prompts
    const promptBtns = document.querySelectorAll(".prompt-btn");

    // Chat History State
    let conversationHistory = [
        {
            role: "assistant",
            content: "Xin chào! Tôi là StrokeGuard AI, trợ lý ảo hỗ trợ thông tin y khoa về đột quỵ (tai biến mạch máu não). Tôi có thể giúp bạn hiểu rõ về triệu chứng nhận biết sớm, hướng dẫn sơ cứu chuẩn y khoa hoặc cách phòng tránh. Bạn muốn hỏi tôi điều gì?"
        }
    ];

    // Initialize Page
    checkSystemStatus();
    loadAllSources();
    setupEventListeners();

    // Event Listeners Setup
    function setupEventListeners() {
        // Close Emergency Banner
        if (closeBannerBtn && emergencyBanner) {
            closeBannerBtn.addEventListener("click", () => {
                emergencyBanner.classList.add("hidden");
            });
        }

        // Tab Switching
        tabActiveSources.addEventListener("click", () => switchTab("active-sources"));
        tabAllSources.addEventListener("click", () => switchTab("all-sources"));

        // Prompt Suggestions
        promptBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const promptText = btn.getAttribute("data-prompt");
                chatInput.value = promptText;
                chatForm.dispatchEvent(new Event("submit"));
            });
        });

        // Chat Form Submission
        chatForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const query = chatInput.value.trim();
            if (!query) return;

            // Clear input
            chatInput.value = "";

            // Add user message to UI & history
            appendMessage("user", query);
            conversationHistory.push({ role: "user", content: query });

            // Show typing indicator
            const typingIndicator = showTypingIndicator();

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ messages: conversationHistory })
                });

                const data = await response.json();
                
                // Remove typing indicator
                typingIndicator.remove();

                if (response.ok) {
                    // Append AI message to UI & history
                    appendMessage("assistant", data.message);
                    conversationHistory.push({ role: "assistant", content: data.message });

                    // Render dynamic references used
                    renderActiveSources(data.sources);
                } else {
                    const errMsg = data.error || "Có lỗi xảy ra khi kết nối tới máy chủ.";
                    appendMessage("assistant", `⚠️ **Lỗi:** ${errMsg}\n\n*Chi tiết:* ${data.detail || "Không có"}`);
                }
            } catch (err) {
                typingIndicator.remove();
                appendMessage("assistant", `⚠️ **Lỗi kết nối:** Không thể kết nối tới máy chủ Flask. Vui lòng kiểm tra xem server đã được khởi chạy chưa.`);
                console.error(err);
            }
        });
    }

    // Check Backend & Ollama health
    async function checkSystemStatus() {
        statusDot.className = "status-dot loading";
        statusText.textContent = "Đang kiểm tra kết nối...";
        
        try {
            const res = await fetch("/api/health");
            const data = await res.json();
            
            if (res.ok && data.status === "healthy") {
                if (data.ollama_connection === "online") {
                    statusDot.className = "status-dot online";
                    statusText.textContent = `Ollama Sẵn Sàng (${data.ollama_model})`;
                    modelBadge.textContent = `Model: ${data.ollama_model}`;
                } else {
                    statusDot.className = "status-dot offline";
                    statusText.textContent = "Ollama Ngoại Tuyến (Chưa bật)";
                    modelBadge.textContent = "Ollama Offline";
                }
            } else {
                statusDot.className = "status-dot offline";
                statusText.textContent = "Lỗi hệ thống";
            }
        } catch (err) {
            statusDot.className = "status-dot offline";
            statusText.textContent = "Mất kết nối Server";
        }
    }

    // Load all scraped sources for the database tab
    async function loadAllSources() {
        try {
            const res = await fetch("/api/sources");
            if (!res.ok) return;
            const sources = await res.json();
            
            totalChunksCount.textContent = sources.length;
            
            if (sources.length === 0) {
                allSourcesList.innerHTML = `<div class="empty-state"><p>Không có dữ liệu cào sẵn.</p></div>`;
                return;
            }

            allSourcesList.innerHTML = "";
            
            // Render a card for each chunk
            sources.forEach(src => {
                const card = document.createElement("div");
                card.className = "source-card";
                card.id = `all-src-${src.id}`;
                
                const badgeClass = src.source.includes("Tâm Anh") ? "badge-tamanh" : "badge-vinmec";
                
                card.innerHTML = `
                    <div class="source-card-header">
                        <span class="source-card-badge badge ${badgeClass}">${src.source}</span>
                        <span class="source-card-id" style="font-size:0.75rem; color:var(--text-muted)">ID: #${src.id}</span>
                    </div>
                    <div class="source-card-title">${src.title}</div>
                    <div class="source-card-section">Mục: ${src.section_title}</div>
                    <a href="${src.url}" target="_blank" rel="noopener" class="source-card-link">
                        Xem bài gốc 🔗
                    </a>
                `;
                allSourcesList.appendChild(card);
            });
        } catch (err) {
            console.error("Error loading sources:", err);
            allSourcesList.innerHTML = `<div class="empty-state"><p>Không thể tải dữ liệu cào.</p></div>`;
        }
    }

    // Switch between reference tabs
    function switchTab(tabName) {
        if (tabName === "active-sources") {
            tabActiveSources.classList.add("active");
            tabAllSources.classList.remove("active");
            paneActiveSources.classList.add("active");
            paneAllSources.classList.remove("active");
        } else {
            tabActiveSources.classList.remove("active");
            tabAllSources.classList.add("active");
            paneActiveSources.classList.remove("active");
            paneAllSources.classList.add("active");
        }
    }

    // Render active sources cited for the current response
    function renderActiveSources(sources) {
        if (!sources || sources.length === 0) {
            activeSourcesEmpty.classList.remove("hidden");
            activeSourcesList.classList.add("hidden");
            return;
        }

        activeSourcesEmpty.classList.add("hidden");
        activeSourcesList.classList.remove("hidden");
        activeSourcesList.innerHTML = "";

        sources.forEach(src => {
            const card = document.createElement("div");
            card.className = "source-card highlighted";
            
            const badgeClass = src.source.includes("Tâm Anh") ? "badge-tamanh" : "badge-vinmec";
            
            card.innerHTML = `
                <div class="source-card-header">
                    <span class="source-card-badge badge ${badgeClass}">${src.source}</span>
                    <span style="font-size:0.75rem; color:var(--text-muted)">ID Match: #${src.id}</span>
                </div>
                <div class="source-card-title">${src.title}</div>
                <div class="source-card-section">Phần đối chiếu: ${src.section_title}</div>
                <div class="source-card-snippet">"${src.snippet}"</div>
                <a href="${src.url}" target="_blank" rel="noopener" class="source-card-link">
                    Xem bài gốc 🔗
                </a>
            `;
            activeSourcesList.appendChild(card);
        });

        // Switch view to active sources tab automatically to highlight citations
        switchTab("active-sources");
    }

    // Append a message bubble to the chat feed
    function appendMessage(role, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}-message`;

        const avatar = role === "user" ? "👤" : "🛡️";
        const parsedHTML = parseMarkdown(text);

        msgDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                ${parsedHTML}
            </div>
        `;

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Show loading typing indicator
    function showTypingIndicator() {
        const indicatorDiv = document.createElement("div");
        indicatorDiv.className = "message assistant-message typing-indicator-container";
        indicatorDiv.innerHTML = `
            <div class="message-avatar">🛡️</div>
            <div class="message-content" style="padding: 10px 14px;">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        chatMessages.appendChild(indicatorDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return indicatorDiv;
    }

    // Extremely lightweight, zero-dependency Markdown parser
    function parseMarkdown(text) {
        let html = text;

        // Escape HTML tags to prevent XSS (since we only want structural styling)
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Restore list formatting (so we can parse lists)
        // Parse bold: **text** -> <strong>text</strong>
        html = html.replace(/\*\*([\s\S]*?)\*\*/g, "<strong>$1</strong>");

        // Parse italic: *text* or _text_ -> <em>text</em>
        html = html.replace(/\*([\s\S]*?)\*/g, "<em>$1</em>");
        html = html.replace(/_([\s\S]*?)_/g, "<em>$1</em>");

        // Parse blockquotes/warnings (like emergency disclaimers)
        html = html.replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>');

        // Parse bullet points
        // Matches lines starting with - or * followed by a space
        const lines = html.split("\n");
        let inList = false;
        let listHTML = [];

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (line.startsWith("- ") || line.startsWith("* ") || line.startsWith("&lt;li&gt;") || line.startsWith("• ")) {
                if (!inList) {
                    listHTML.push("<ul>");
                    inList = true;
                }
                const content = line.substring(2);
                listHTML.push(`<li>${content}</li>`);
            } else {
                if (inList) {
                    listHTML.push("</ul>");
                    inList = false;
                }
                listHTML.push(lines[i]);
            }
        }
        if (inList) {
            listHTML.push("</ul>");
        }
        
        html = listHTML.join("\n");

        // Replace double line breaks with paragraph tags
        html = html.split("\n\n").map(p => {
            p = p.trim();
            if (!p) return "";
            if (p.startsWith("<ul") || p.startsWith("<ol") || p.startsWith("<blockquote")) return p;
            return `<p>${p.replace(/\n/g, "<br>")}</p>`;
        }).join("");

        return html;
    }
});
