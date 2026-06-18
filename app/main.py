import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import Database
from app.rag import RAGManager

# Inicializa o FastAPI
app = FastAPI(title="ShopFlow Support Agent API", version="1.0")

# Habilita CORS para facilitar desenvolvimento local se necessário
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa banco de dados e RAG
db = Database()
rag = RAGManager()

# Estrutura simples de Rate Limiting em memória (Armazena IP -> [timestamps])
rate_limit_db = {}
MAX_REQUESTS_PER_MINUTE = 6

def check_rate_limit(ip: str, bypass: bool = False):
    """
    Controla o limite de requisições por IP.
    Permite bypass caso o cliente esteja usando chave de API própria.
    """
    if bypass:
        return
        
    now = datetime.now().timestamp()
    if ip not in rate_limit_db:
        rate_limit_db[ip] = []
        
    # Remove timestamps mais antigos que 60 segundos
    rate_limit_db[ip] = [ts for ts in rate_limit_db[ip] if now - ts < 60]
    
    if len(rate_limit_db[ip]) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=429, 
            detail="Muitas requisições. Limite de 6 mensagens por minuto excedido para evitar abuso da cota pública."
        )
        
    rate_limit_db[ip].append(now)

# Modelos Pydantic para os Endpoints
class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID único da conversa")
    message: str = Field(..., description="Mensagem do cliente")
    threshold: float = Field(0.25, description="Limiar de confiança para RAG")

class EscalateRequest(BaseModel):
    session_id: str
    reason: Optional[str] = "Solicitado manualmente pelo usuário"

# Endpoints da API

@app.post("/api/chat")
async def chat_endpoint(
    request: Request, 
    chat_req: ChatRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    # Identifica o IP do cliente para o rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # Se há chave customizada enviada pelo cliente no header, ignora o rate limit
    has_custom_key = bool(x_gemini_key and x_gemini_key.strip())
    check_rate_limit(client_ip, bypass=has_custom_key)
    
    session_id = chat_req.session_id
    user_msg = chat_req.message.strip()
    threshold = chat_req.threshold
    
    if not user_msg:
        raise HTTPException(status_code=400, detail="A mensagem não pode ser vazia.")
        
    # 1. Carrega a conversa atual
    conv = db.get_conversation(session_id)
    
    # Se já foi escalada, o suporte humano deve responder. Simulamos isso.
    if conv["status"] == "escalated":
        escalated_msg = "A conversa está na fila de atendimento humano. Nossos agentes entrarão em contato em instantes."
        db.add_message(session_id, "user", user_msg)
        db.add_message(session_id, "agent", escalated_msg, confidence=1.0)
        return {
            "answer": escalated_msg,
            "sources": [],
            "confidence": 1.0,
            "escalated": True,
            "reason": "Conversa já escalada anteriormente"
        }
        
    # 2. Adiciona mensagem do usuário ao banco
    db.add_message(session_id, "user", user_msg)
    
    # 3. Executa RAG e busca resposta
    chat_history = conv["messages"]
    rag_result = rag.answer_query(
        query=user_msg, 
        chat_history=chat_history[:-1], # Remove a última msg recém inserida para evitar duplicidade
        min_confidence=threshold,
        custom_api_key=x_gemini_key
    )
    
    # 4. Registra a resposta da IA no banco
    db.add_message(
        session_id=session_id,
        sender="agent",
        text=rag_result["answer"],
        sources=rag_result["sources"],
        confidence=rag_result["confidence"],
        escalated=rag_result.get("escalated", False),
        reason=rag_result.get("reason")
    )
    
    # 5. Se o resultado do RAG exigir escalação, marca no banco
    if rag_result.get("escalated"):
        db.escalate_conversation(session_id, reason=rag_result.get("reason", "Baixa confiança"))
        
    return rag_result

@app.post("/api/escalate")
async def escalate_endpoint(escalate_req: EscalateRequest):
    """
    Endpoint para escalação manual pelo botão da interface.
    """
    db.escalate_conversation(escalate_req.session_id, reason=escalate_req.reason)
    return {"status": "success", "message": "Conversa escalada para atendimento humano."}

@app.get("/api/metrics")
async def metrics_endpoint():
    """
    Retorna as métricas e o log de tickets recentes para o Dashboard.
    """
    metrics = db.get_metrics()
    recent_tickets = db.get_recent_tickets(limit=15)
    return {
        "metrics": metrics,
        "recent_tickets": recent_tickets
    }

@app.post("/api/reset")
async def reset_endpoint():
    """
    Reseta o banco de dados de conversas e limpa o dashboard.
    """
    db.reset_db()
    return {"status": "success", "message": "Dados resetados com sucesso."}

@app.get("/api/conversation/{session_id}")
async def get_conversation_endpoint(session_id: str):
    """
    Retorna o histórico de uma conversa específica pelo ID.
    """
    return db.get_conversation(session_id)

@app.get("/api/articles")
async def get_articles_endpoint():
    """
    Retorna a lista de todos os artigos da base de conhecimento.
    """
    return rag.articles

@app.get("/health")
async def health_endpoint():
    return {
        "status": "healthy",
        "articles_loaded": len(rag.articles),
        "rate_limiting_active_ips": len(rate_limit_db)
    }

# Servir os arquivos estáticos do frontend (HTML/CSS/JS)
# Importante montar por último para não sobrepor as rotas da API
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
