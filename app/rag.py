import os
import json
from typing import Dict, List, Any, Tuple, Optional

# Importações do LangChain e ChromaDB
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

from app.indexer import parse_docx, run_indexing

class RAGManager:
    def __init__(self, doc_path: str = "ShopFlow_KnowledgeBase.docx", 
                 articles_json_path: str = "data/articles.json"):
        self.doc_path = doc_path
        self.articles_json_path = articles_json_path
        self.articles: List[Dict[str, Any]] = []
        
        # Inicializa o modelo de embeddings local via HuggingFace
        # all-MiniLM-L6-v2 gera vetores de 384 dimensões rapidamente em CPU
        print("Carregando modelo de embeddings local (all-MiniLM-L6-v2)...")
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        self.vector_store = None
        self.initialize_data()

    def initialize_data(self):
        """
        Carrega os artigos processados do arquivo JSON.
        Se o JSON não existir, dispara a indexação do docx automaticamente.
        Em seguida, indexa os documentos no banco vetorial ChromaDB.
        """
        # Se o arquivo de artigos não existe, tenta gerar
        if not os.path.exists(self.articles_json_path):
            doc_file = self.doc_path
            if not os.path.exists(doc_file):
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                doc_file = os.path.join(base_dir, self.doc_path)
                
            if os.path.exists(doc_file):
                print("Indexador disparado automaticamente por ausência de data/articles.json...")
                self.articles = run_indexing(doc_file, self.articles_json_path)
            else:
                print(f"AVISO: Arquivo docx não encontrado em {self.doc_path}. Tentando carregar JSON existente...")
                
        # Carrega o JSON
        if os.path.exists(self.articles_json_path):
            with open(self.articles_json_path, "r", encoding="utf-8") as f:
                self.articles = json.load(f)
            print(f"Sucesso: {len(self.articles)} artigos carregados do JSON.")
            self._build_vector_store()
        else:
            print("ERRO: Nenhuma base de conhecimento disponível na inicialização.")

    def _build_vector_store(self):
        """
        Converte os artigos carregados em objetos Document do LangChain 
        e cria o banco vetorial ChromaDB em memória.
        """
        if not self.articles:
            return
            
        print("Criando banco vetorial ChromaDB com LangChain...")
        documents = []
        for art in self.articles:
            # Combinamos título, categoria e conteúdo para o índice semântico do vetor
            page_content = f"Título: {art['title']}\nCategoria: {art['category']}\nConteúdo: {art['content']}"
            metadata = {
                "number": art["number"],
                "title": art["title"],
                "category": art["category"],
                "content": art["content"]
            }
            documents.append(Document(page_content=page_content, metadata=metadata))
            
        # Criamos o banco vetorial em memória para máxima portabilidade no Hugging Face
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings
        )
        print("Banco vetorial ChromaDB inicializado com sucesso!")

    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """
        Busca os artigos mais similares à query usando o ChromaDB e LangChain.
        Retorna uma lista de tuplas (Artigo, score_similaridade_cosseno).
        """
        if not self.articles or self.vector_store is None:
            return []

        # Realiza a busca vetorial retornando scores de relevância (distância de cosseno mapeada de 0 a 1)
        results = self.vector_store.similarity_search_with_relevance_scores(query, k=top_k)
        
        retrieved_articles = []
        for doc, score in results:
            art = {
                "number": doc.metadata["number"],
                "title": doc.metadata["title"],
                "category": doc.metadata["category"],
                "content": doc.metadata["content"]
            }
            retrieved_articles.append((art, float(score)))
            
        return retrieved_articles

    def answer_query(self, query: str, chat_history: List[Dict[str, Any]], 
                     min_confidence: float = 0.35, 
                     custom_api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Processa a pergunta, executa a busca vetorial via ChromaDB e gera a resposta via Gemini
        orquestrada pelo LangChain (ou via fallback mock).
        """
        # 1. Recuperação semântica (Retrieval)
        retrieved = self.retrieve(query, top_k=3)
        
        if not retrieved:
            return {
                "answer": "Desculpe, nossa base de conhecimento está indisponível no momento. Estou transferindo você para um atendente humano.",
                "sources": [],
                "confidence": 0.0,
                "escalated": True,
                "reason": "Sem artigos na base de dados"
            }
            
        # Pega o melhor artigo correspondente e seu score
        best_art, best_score = retrieved[0]
        
        # 2. Verificação de Confiança da Busca (Threshold semântico)
        if best_score < min_confidence:
            return {
                "answer": f"Entendi que sua dúvida é sobre algo que não encontrei em nossa base de conhecimento padrão (Confiança Semântica: {best_score:.2f} < Limiar: {min_confidence:.2f}). Estou transferindo você para o suporte humano agora para te ajudar melhor!",
                "sources": [best_art],
                "confidence": best_score,
                "escalated": True,
                "reason": f"Baixa confiança na busca vetorial (Score: {best_score:.2f} < {min_confidence:.2f})"
            }

        # Filtrar as fontes que possuem relevância aceitável
        sources = [art for art, score in retrieved if score > 0.45]
        if not sources:
            sources = [best_art]
        
        # 3. Escolher a chave de API do Gemini
        api_key = custom_api_key or os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            # --- Modo Fallback / Mock Inteligente (Sem Chave API) ---
            fallback_answer = (
                f"**[Modo Demonstrativo - Sem Chave API (LangChain + ChromaDB)]**\n\n"
                f"Aqui está a solução que encontrei em nossa base de dados para **\"{best_art['title']}\"** ({best_art['category']}):\n\n"
                f"{best_art['content']}\n\n"
                f"*Nota: Insira sua chave Gemini API na barra lateral para testar a geração de respostas completas da LLM via LangChain.*"
            )
            return {
                "answer": fallback_answer,
                "sources": sources,
                "confidence": best_score,
                "escalated": False,
                "mode": "fallback_mock"
            }

        # 4. Geração com LLM usando LangChain
        try:
            # Inicializa a LLM do Gemini integrada ao LangChain
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=api_key,
                temperature=0.2
            )
            
            # Formata o contexto dos artigos relevantes
            context_text = ""
            for idx, art in enumerate(sources):
                context_text += f"Artigo [{idx + 1}]: {art['title']}\nCategoria: {art['category']}\nConteúdo:\n{art['content']}\n\n"
                
            # Formata o histórico do chat
            history_text = ""
            for msg in chat_history[-6:]:
                role = "Cliente" if msg["sender"] == "user" else "Atendente"
                history_text += f"{role}: {msg['text']}\n"
                
            prompt = f"""Você é o atendente de suporte inteligente da ShopFlow. Seu objetivo é ajudar os clientes respondendo às perguntas de maneira educada e precisa, utilizando unicamente os artigos da Base de Conhecimento fornecidos abaixo.

Diretrizes Críticas:
1. Responda apenas com base nas informações contidas nos artigos fornecidos no Contexto. Seja fiel à base de dados.
2. Se a pergunta do usuário não puder ser respondida usando os artigos fornecidos ou se as informações forem totalmente insuficientes, responda exatamente com a palavra "[ESCALAR]" acompanhada de uma mensagem amigável explicando que você não tem essa informação específica e que estará transferindo para um atendente humano.
3. Ao responder, no final da resposta, mencione qual artigo você utilizou como base para a sua resposta (a fonte). Ex: "(Fonte: Artigo X – [Título do Artigo])".
4. Mantenha um tom profissional, amigável, prestativo e em português.

Contexto dos artigos da ShopFlow:
{context_text}

Histórico recente da conversa:
{history_text}

Pergunta do usuário: {query}
Resposta:"""

            # Executa a geração de conteúdo do LangChain
            response = llm.invoke(prompt)
            answer = response.content.strip()
            
            # 5. Verifica se a LLM solicitou a escalação humana
            if "[ESCALAR]" in answer or "[escalar]" in answer:
                clean_answer = answer.replace("[ESCALAR]", "").replace("[escalar]", "").strip()
                if not clean_answer:
                    clean_answer = "Não encontrei essa informação na base de dados. Estou transferindo você para um atendente humano."
                return {
                    "answer": clean_answer,
                    "sources": sources,
                    "confidence": best_score,
                    "escalated": True,
                    "reason": "Solicitado pela LLM (Incerteza no Contexto)"
                }
                
            return {
                "answer": answer,
                "sources": sources,
                "confidence": best_score,
                "escalated": False,
                "mode": "langchain_generation"
            }
            
        except Exception as e:
            print(f"Erro ao chamar LangChain / Gemini API: {e}")
            fallback_answer = (
                f"**[Erro na Integração LangChain - Fallback Ativado]**\n\n"
                f"Obtive a resposta diretamente do banco vetorial ChromaDB:\n\n"
                f"{best_art['content']}\n\n"
                f"*(Detalhes do erro: {str(e)})*"
            )
            return {
                "answer": fallback_answer,
                "sources": sources,
                "confidence": best_score,
                "escalated": False,
                "mode": "error_fallback"
            }
