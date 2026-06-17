// ==========================================================================
// ESTADO GLOBAL DA APLICAÇÃO
// ==========================================================================
let state = {
    sessionId: "",
    apiKey: "",
    threshold: 0.35,
    isEscalated: false,
    activeTab: "chat",
    charts: {
        resolutions: null,
        categories: null
    }
};

// ==========================================================================
// INICIALIZAÇÃO DA APLICAÇÃO
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    // 1. Gera ou recupera o Session ID
    initSession();
    
    // 2. Carrega configurações do localStorage
    loadConfig();
    
    // 3. Inicializa os ícones Lucide
    lucide.createIcons();
    
    // 4. Carrega histórico do chat se a sessão for nova ou existente
    loadActiveChat();
});

function initSession() {
    let savedSession = sessionStorage.getItem("shopflow_session_id");
    if (!savedSession) {
        const rand = Math.floor(1000 + Math.random() * 9000);
        savedSession = `SF-${rand}`;
        sessionStorage.setItem("shopflow_session_id", savedSession);
    }
    state.sessionId = savedSession;
    document.getElementById("session-id-display").innerText = savedSession;
}

function loadConfig() {
    // Carrega API Key
    const savedKey = localStorage.getItem("shopflow_gemini_key") || "";
    state.apiKey = savedKey;
    document.getElementById("gemini-key-input").value = savedKey;
    
    // Fixa o limiar padrão para detecção de incerteza
    state.threshold = 0.35;
}

// ==========================================================================
// CONTROLES DE CONFIGURAÇÃO (SIDEBAR)
// ==========================================================================
function saveApiKey() {
    const key = document.getElementById("gemini-key-input").value.strip ? 
                document.getElementById("gemini-key-input").value.strip() : 
                document.getElementById("gemini-key-input").value;
    state.apiKey = key;
    localStorage.setItem("shopflow_gemini_key", key);
}

function togglePasswordVisibility() {
    const input = document.getElementById("gemini-key-input");
    const icon = document.getElementById("eye-icon");
    
    if (input.type === "password") {
        input.type = "text";
        icon.setAttribute("data-lucide", "eye-off");
    } else {
        input.type = "password";
        icon.setAttribute("data-lucide", "eye");
    }
    lucide.createIcons();
}

async function resetSystemData() {
    if (confirm("Deseja realmente limpar todos os tickets e logs de teste? Essa ação não pode ser desfeita.")) {
        try {
            const response = await fetch("/api/reset", { method: "POST" });
            const data = await response.json();
            if (response.ok) {
                alert("Banco de dados resetado com sucesso!");
                // Reinicia sessão
                sessionStorage.removeItem("shopflow_session_id");
                initSession();
                state.isEscalated = false;
                document.getElementById("escalation-banner").style.display = "none";
                enableChatInputs();
                
                // Limpa o chat e põe a intro
                clearChatUI();
                
                // Recarrega se estiver no dashboard
                if (state.activeTab === "dashboard") {
                    fetchMetrics();
                }
            } else {
                alert(`Erro: ${data.detail}`);
            }
        } catch (e) {
            console.error(e);
            alert("Erro ao tentar conectar com a API.");
        }
    }
}

// ==========================================================================
// NAVEGAÇÃO DE TABS
// ==========================================================================
function switchTab(tabName) {
    state.activeTab = tabName;
    
    // Atualiza classes ativas nos botões do menu
    document.getElementById("btn-tab-chat").classList.toggle("active", tabName === "chat");
    document.getElementById("btn-tab-dashboard").classList.toggle("active", tabName === "dashboard");
    
    // Mostra/oculta seções
    document.getElementById("tab-chat").classList.toggle("active", tabName === "chat");
    document.getElementById("tab-dashboard").classList.toggle("active", tabName === "dashboard");
    
    if (tabName === "dashboard") {
        fetchMetrics();
    }
}

// ==========================================================================
// LÓGICA E UI DO CHAT
// ==========================================================================
function clearChatUI() {
    const chatHistory = document.getElementById("chat-history");
    chatHistory.innerHTML = `
        <div class="chat-message agent system-intro">
            <div class="message-avatar"><i data-lucide="bot"></i></div>
            <div class="message-bubble">
                <p>Olá! Eu sou o assistente virtual da **ShopFlow**. Posso te ajudar com dúvidas sobre pagamentos, integrações, onboarding, erros, cancelamentos e planos.</p>
                <p>Aqui estão algumas dúvidas frequentes que posso responder com precisão:</p>
                <div class="quick-suggest-grid">
                    <button class="btn-suggest" onclick="sendSuggestedQuestion('Meu pagamento foi recusado. O que fazer?')">
                        Meu pagamento foi recusado. O que fazer?
                    </button>
                    <button class="btn-suggest" onclick="sendSuggestedQuestion('Como integrar com a API de frete?')">
                        Como integrar com a API de frete?
                    </button>
                    <button class="btn-suggest" onclick="sendSuggestedQuestion('Qual o prazo de devolução de um produto?')">
                        Qual o prazo de devolução?
                    </button>
                    <button class="btn-suggest" onclick="sendSuggestedQuestion('Como alterar meu plano mensal?')">
                        Como alterar meu plano mensal?
                    </button>
                </div>
            </div>
        </div>
    `;
    lucide.createIcons();
}

async function loadActiveChat() {
    try {
        const response = await fetch(`/api/conversation/${state.sessionId}`);
        if (response.ok) {
            const conv = await response.json();
            if (conv.messages && conv.messages.length > 0) {
                // Limpa o chat para reconstruir a partir das mensagens salvas
                const chatHistory = document.getElementById("chat-history");
                chatHistory.innerHTML = "";
                
                conv.messages.forEach(msg => {
                    appendMessageBubble(msg.sender, msg.text, msg.sources, msg.confidence, msg.escalated, msg.reason);
                });
                
                if (conv.status === "escalated") {
                    state.isEscalated = true;
                    showEscalationBanner();
                    disableChatInputs();
                } else {
                    state.isEscalated = false;
                    hideEscalationBanner();
                    enableChatInputs();
                }
                scrollToBottom();
            }
        }
    } catch (e) {
        console.error("Erro ao carregar chat ativo:", e);
    }
}

async function loadPreviousConversation(sessId) {
    state.sessionId = sessId;
    document.getElementById("session-id-display").innerText = sessId;
    sessionStorage.setItem("shopflow_session_id", sessId);
    
    // Troca de aba
    switchTab("chat");
    
    // Carrega o chat
    await loadActiveChat();
}

function scrollToBottom() {
    const chatHistory = document.getElementById("chat-history");
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function formatMarkdown(text) {
    // Formatação super simples para **bold** e listas
    let html = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
    return html;
}

function appendMessageBubble(sender, text, sources = null, confidence = null, escalated = false, reason = null) {
    const chatHistory = document.getElementById("chat-history");
    
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("chat-message", sender);
    
    const avatarDiv = document.createElement("div");
    avatarDiv.classList.add("message-avatar");
    avatarDiv.innerHTML = sender === "user" ? '<i data-lucide="user"></i>' : '<i data-lucide="bot"></i>';
    
    const bubbleDiv = document.createElement("div");
    bubbleDiv.classList.add("message-bubble");
    
    // Formata o corpo da mensagem
    let textHtml = formatMarkdown(text);
    bubbleDiv.innerHTML = `<p>${textHtml}</p>`;
    
    // Se for o agente e possuir fontes RAG, renderiza a seção do Raio-X da Decisão
    if (sender === "agent" && sources && sources.length > 0) {
        const xrayId = `xray-${Math.floor(Math.random() * 1000000)}`;
        const xraySection = document.createElement("div");
        xraySection.classList.add("message-xray");
        
        // Pega o melhor artigo correspondente (primeiro da lista de retorno do ChromaDB)
        const bestSrc = sources[0];
        const scoreVal = confidence !== null ? confidence.toFixed(2) : "0.00";
        
        // Configura rótulos e classes de acordo com a decisão cognitiva
        let decisionTitle = "Resolução Aprovada";
        let decisionClass = "resolved";
        let decisionIcon = "shield-check";
        let decisionDesc = `O Agente analisou a pergunta e confirmou que o <strong>Artigo ${bestSrc.number}</strong> contém a resposta exata. Ele estruturou uma resposta amigável e direta baseada na base.`;
        
        if (escalated) {
            decisionTitle = "Escalação Preventiva";
            decisionClass = "escalated";
            decisionIcon = "user-x";
            
            // Personaliza a explicação se for o exemplo clássico de frete
            if (text.toLowerCase().includes("frete") || reason.toLowerCase().includes("frete")) {
                decisionDesc = `O Agente leu o <strong>Artigo ${bestSrc.number}</strong> (geração de chaves API) e percebeu que ele <strong>NÃO responde</strong> à dúvida específica sobre integração de frete. Para evitar alucinações e erros operacionais, o Agente bloqueou a resposta automática e acionou o suporte humano.<br><small><strong>Motivo:</strong> ${reason || "Incerteza no contexto"}</small>`;
            } else {
                decisionDesc = `O Agente analisou o artigo mais próximo recuperado pela busca vetorial. Como as informações foram julgadas <strong>insuficientes ou irrelevantes</strong> para responder com precisão, o Agente ativou a salvaguarda de escalação.<br><small><strong>Motivo:</strong> ${reason || "Baixa confiança"}</small>`;
            }
        }
        
        // Constrói os cards das outras fontes se houver mais de uma
        let extraSourcesHtml = "";
        if (sources.length > 1) {
            extraSourcesHtml = `<div class="extra-sources-title">Outros artigos buscados:</div>`;
            sources.slice(1).forEach(src => {
                extraSourcesHtml += `
                    <div class="extra-source-item">
                        <span>Artigo ${src.number} – ${src.title} (${src.category})</span>
                    </div>
                `;
            });
        }
        
        xraySection.innerHTML = `
            <button class="xray-toggle" onclick="toggleXrayUI('${xrayId}', this)">
                <i data-lucide="scan-eye"></i>
                <span>Ver Raio-X da Decisão (ChromaDB vs. Agente)</span>
            </button>
            <div class="xray-content" id="${xrayId}">
                <div class="xray-split">
                    <!-- Coluna do Algoritmo de Busca -->
                    <div class="xray-col algorithm">
                        <div class="col-header">
                            <i data-lucide="binary"></i>
                            <span>Fase 1: Busca Vetorial (ChromaDB)</span>
                        </div>
                        <div class="xray-card">
                            <div class="xray-card-row">
                                <span class="card-label">Mais Similar:</span>
                                <span class="card-val highlight">Artigo ${bestSrc.number}</span>
                            </div>
                            <div class="xray-card-row">
                                <span class="card-label">Distância Semântica:</span>
                                <span class="card-val score-badge">Score: ${scoreVal}</span>
                            </div>
                            <div class="xray-card-row title-row">
                                <span class="card-label">Título:</span>
                                <span class="card-val">${bestSrc.title}</span>
                            </div>
                            <div class="article-preview">
                                <strong>Trecho extraído do Docx:</strong>
                                <p>${bestSrc.content}</p>
                            </div>
                            ${extraSourcesHtml}
                            <span class="xray-explanation-note">
                                * Um buscador tradicional exibiria esse texto diretamente para o cliente, mesmo sem responder à dúvida.
                            </span>
                        </div>
                    </div>
                    
                    <!-- Coluna do Agente Cognitivo -->
                    <div class="xray-col agent ${decisionClass}">
                        <div class="col-header">
                            <i data-lucide="brain"></i>
                            <span>Fase 2: Decisão Cognitiva (LLM)</span>
                        </div>
                        <div class="xray-card">
                            <div class="decision-badge ${decisionClass}">
                                <i data-lucide="${decisionIcon}"></i>
                                <span>Status: ${decisionTitle}</span>
                            </div>
                            <div class="decision-desc">
                                <p>${decisionDesc}</p>
                            </div>
                            <span class="xray-explanation-note">
                                * O Agente analisa criticamente se a informação é de fato suficiente para responder com total segurança.
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        bubbleDiv.appendChild(xraySection);
    }
    
    // Se for mensagem de sistema
    if (sender === "system") {
        const sysDiv = document.createElement("div");
        sysDiv.classList.add("chat-message", "system-intro");
        sysDiv.style.alignSelf = "center";
        sysDiv.style.maxWidth = "90%";
        
        const sysBubble = document.createElement("div");
        sysBubble.classList.add("message-bubble");
        sysBubble.style.background = "rgba(245, 158, 11, 0.08)";
        sysBubble.style.border = "1px dashed rgba(245, 158, 11, 0.3)";
        sysBubble.style.color = "var(--color-warning)";
        sysBubble.style.fontSize = "12px";
        sysBubble.style.padding = "10px 16px";
        sysBubble.style.borderRadius = "8px";
        sysBubble.innerHTML = `<i data-lucide="alert-triangle" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:8px;"></i>${text}`;
        
        sysDiv.appendChild(sysBubble);
        chatHistory.appendChild(sysDiv);
        lucide.createIcons();
        return;
    }

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(bubbleDiv);
    chatHistory.appendChild(messageDiv);
    
    // Atualiza ícones para que os novos apareçam
    lucide.createIcons();
}

function toggleXrayUI(id, button) {
    const content = document.getElementById(id);
    const isShowing = content.classList.toggle("show");
    button.classList.toggle("active", isShowing);
}

function sendSuggestedQuestion(question) {
    if (state.isEscalated) return;
    document.getElementById("chat-input").value = question;
    document.getElementById("chat-form").requestSubmit();
}

function disableChatInputs() {
    document.getElementById("chat-input").disabled = true;
    document.getElementById("btn-manual-escalate").classList.add("disabled");
    document.getElementById("btn-manual-escalate").disabled = true;
    document.getElementById("btn-submit-send").disabled = true;
    document.getElementById("chat-input").placeholder = "Chat desativado - Atendimento em fila humana";
}

function enableChatInputs() {
    document.getElementById("chat-input").disabled = false;
    document.getElementById("btn-manual-escalate").classList.remove("disabled");
    document.getElementById("btn-manual-escalate").disabled = false;
    document.getElementById("btn-submit-send").disabled = false;
    document.getElementById("chat-input").placeholder = "Digite sua dúvida aqui...";
}

function showEscalationBanner() {
    document.getElementById("escalation-banner").style.display = "flex";
}

function hideEscalationBanner() {
    document.getElementById("escalation-banner").style.display = "none";
}

async function handleChatSubmit(event) {
    event.preventDefault();
    if (state.isEscalated) return;
    
    const input = document.getElementById("chat-input");
    const query = input.value.trim();
    if (!query) return;
    
    // 1. Mostra a mensagem do usuário
    appendMessageBubble("user", query);
    input.value = "";
    scrollToBottom();
    
    // 2. Mostra indicador de digitação
    const typingIndicator = document.getElementById("typing-indicator");
    typingIndicator.style.display = "flex";
    scrollToBottom();
    
    // 3. Desativa inputs temporariamente
    document.getElementById("btn-submit-send").disabled = true;
    input.disabled = true;

    try {
        const headers = {
            "Content-Type": "application/json"
        };
        if (state.apiKey) {
            headers["X-Gemini-Key"] = state.apiKey;
        }
        
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                session_id: state.sessionId,
                message: query,
                threshold: state.threshold
            })
        });
        
        const data = await response.json();
        
        // Oculta indicador
        typingIndicator.style.display = "none";
        
        if (response.ok) {
            appendMessageBubble("agent", data.answer, data.sources, data.confidence, data.escalated, data.reason);
            
            if (data.escalated) {
                state.isEscalated = true;
                showEscalationBanner();
                disableChatInputs();
                appendMessageBubble("system", `Conversa escalada automaticamente. Motivo: ${data.reason}`);
            } else {
                // Re-habilita inputs
                input.disabled = false;
                document.getElementById("btn-submit-send").disabled = false;
                input.focus();
            }
        } else {
            // Se der erro por rate limiting ou técnico
            appendMessageBubble("system", `Erro técnico: ${data.detail || "Não foi possível processar a resposta."}`);
            input.disabled = false;
            document.getElementById("btn-submit-send").disabled = false;
        }
    } catch (e) {
        typingIndicator.style.display = "none";
        appendMessageBubble("system", "Falha de conexão com o servidor de suporte.");
        input.disabled = false;
        document.getElementById("btn-submit-send").disabled = false;
        console.error(e);
    }
    scrollToBottom();
}

async function manualEscalate() {
    if (state.isEscalated) return;
    if (confirm("Você deseja transferir esta conversa para o atendimento humano?")) {
        try {
            const response = await fetch("/api/escalate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    reason: "Solicitado manualmente pelo usuário"
                })
            });
            if (response.ok) {
                state.isEscalated = true;
                showEscalationBanner();
                disableChatInputs();
                appendMessageBubble("system", "Você solicitou o atendimento humano. Um atendente entrará no chat em breve.");
                scrollToBottom();
            }
        } catch (e) {
            console.error("Erro ao escalar conversa:", e);
            alert("Erro ao registrar a solicitação de escalação.");
        }
    }
}

// ==========================================================================
// PAINEL DE MÉTRICAS E GRÁFICOS (DASHBOARD)
// ==========================================================================
async function fetchMetrics() {
    try {
        const response = await fetch("/api/metrics");
        if (!response.ok) return;
        
        const data = await response.json();
        const m = data.metrics;
        const recent = data.recent_tickets;
        
        // 1. Atualizar os cards numéricos
        document.getElementById("metric-deflection-rate").innerText = `${m.deflection_rate}%`;
        document.getElementById("metric-total-tickets").innerText = m.total_tickets;
        document.getElementById("metric-resolved-tickets").innerText = m.resolved_tickets;
        document.getElementById("metric-escalated-tickets").innerText = m.escalated_tickets;
        
        // 2. Gráfico de Rosca: Resolvidos vs Escalados
        renderResolutionsChart(m.resolved_tickets, m.escalated_tickets);
        
        // 3. Gráfico de Barras: Dúvidas por Categorias
        renderCategoriesChart(m.category_distribution);
        
        // 4. Preencher Tabela de Tickets Recentes
        renderTicketsTable(recent);
        
    } catch (e) {
        console.error("Erro ao buscar métricas:", e);
    }
}

function renderResolutionsChart(resolved, escalated) {
    const ctx = document.getElementById("resolutionsChart").getContext("2d");
    
    // Destrói gráfico anterior se existir
    if (state.charts.resolutions) {
        state.charts.resolutions.destroy();
    }
    
    if (resolved === 0 && escalated === 0) {
        // Se sem dados, coloca mock
        resolved = 1;
        escalated = 0;
    }

    state.charts.resolutions = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Resolvidos (IA)", "Escalados para Humano"],
            datasets: [{
                data: [resolved, escalated],
                backgroundColor: ["#10b981", "#ef4444"],
                borderColor: ["rgba(16, 185, 129, 0.3)", "rgba(239, 68, 68, 0.3)"],
                borderWidth: 1,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        color: "#9ca3af",
                        font: { family: "Plus Jakarta Sans", size: 11 }
                    }
                }
            },
            cutout: "70%"
        }
    });
}

function renderCategoriesChart(categoryDist) {
    const ctx = document.getElementById("categoriesChart").getContext("2d");
    
    if (state.charts.categories) {
        state.charts.categories.destroy();
    }
    
    let labels = [];
    let counts = [];
    
    if (categoryDist && categoryDist.length > 0) {
        // Pega as top 5 categorias ou mais
        categoryDist.forEach(item => {
            // Simplifica a string da categoria tirando "Categoria X:"
            const cleanLabel = item.category.replace(/^Categoria\s+\d+:\s*/i, "");
            labels.push(cleanLabel);
            counts.push(item.count);
        });
    } else {
        // Mock se não houver dados
        labels = ["Pagamentos", "APIs & Integrações", "Onboarding", "Cancelamentos", "Erros & Bugs", "Planos"];
        counts = [0, 0, 0, 0, 0, 0];
    }
    
    state.charts.categories = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Acessos aos Artigos",
                data: counts,
                backgroundColor: "rgba(139, 92, 246, 0.4)",
                borderColor: "#8b5cf6",
                borderWidth: 1.5,
                borderRadius: 6,
                hoverBackgroundColor: "rgba(139, 92, 246, 0.7)"
            }]
        },
        options: {
            indexAxis: "y", // Gráfico de barras horizontais
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#9ca3af", stepSize: 1, precision: 0 }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: "#9ca3af", font: { family: "Plus Jakarta Sans", size: 10 } }
                }
            }
        }
    });
}

function renderTicketsTable(tickets) {
    const body = document.getElementById("tickets-table-body");
    body.innerHTML = "";
    
    if (!tickets || tickets.length === 0) {
        body.innerHTML = '<tr><td colspan="6" class="text-center">Nenhum atendimento registrado.</td></tr>';
        return;
    }
    
    tickets.forEach(t => {
        // Formata data e hora
        const dateObj = new Date(t.updated_at);
        const formatTime = dateObj.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
        const formatDate = dateObj.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
        
        let statusText = "";
        let statusClass = "";
        
        if (t.status === "resolved") {
            statusText = "Resolvido";
            statusClass = "resolved";
        } else if (t.status === "escalated") {
            statusText = "Escalado";
            statusClass = "escalated";
        } else {
            statusText = "Em Progresso";
            statusClass = "in_progress";
        }
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${t.session_id}</strong></td>
            <td>${t.last_query}</td>
            <td>${formatDate} às ${formatTime}</td>
            <td>${t.message_count}</td>
            <td>
                <span class="status-badge ${statusClass}">
                    ${statusText}
                </span>
            </td>
            <td>
                <button class="btn-table-action" onclick="loadPreviousConversation('${t.session_id}')">
                    Ver Conversa
                </button>
            </td>
        `;
        body.appendChild(tr);
    });
}
