import os
import json
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai

from app.indexer import parse_docx, run_indexing

PORTUGUESE_STOP_WORDS = [
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "para", "com", "por", "que", "se", "como", "mais", "mas", "ou",
    "este", "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquela",
    "qual", "quais", "quem", "cujo", "cuja", "cujos", "cujas",
    "me", "te", "se", "nos", "vos", "lhe", "lhes",
    "meu", "minha", "meus", "minhas", "teu", "tua", "teus", "tuas",
    "seu", "sua", "seus", "suas", "nosso", "nossa", "nossos", "nossas",
    "ele", "ela", "eles", "elas", "eu", "tu", "você", "vocês", "nós", "vós",
    "ser", "estar", "ter", "haver", "fazer",
    "é", "são", "era", "eram", "foi", "foram", "seria", "seriam",
    "esta", "está", "estão", "estava", "estavam", "estive", "estiveram",
    "tem", "têm", "tinha", "tinham", "tive", "tiveram",
    "há", "havia", "haviam", "houve", "houveram", "ao", "aos", "à", "às", "daqui", "dali"
]

class RAGManager:
    def __init__(self, doc_path: str = "ShopFlow_KnowledgeBase.docx", 
                 articles_json_path: str = "data/articles.json"):
        self.doc_path = doc_path
        self.articles_json_path = articles_json_path
        self.articles: List[Dict[str, Any]] = []
        self.vectorizer = TfidfVectorizer(stop_words=PORTUGUESE_STOP_WORDS)
        self.tfidf_matrix = None
        
        self.initialize_data()

    def initialize_data(self):
        """
        Carrega os artigos processados do arquivo JSON.
        Se o JSON não existir, dispara a indexação do docx automaticamente.
        """
        # Se o arquivo de artigos não existe, tenta gerar
        if not os.path.exists(self.articles_json_path):
            # Procura pelo arquivo docx
            doc_file = self.doc_path
            if not os.path.exists(doc_file):
                # Tenta no diretório pai se estiver rodando de dentro de /app
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                doc_file = os.path.join(base_dir, self.doc_path)
                
            if os.path.exists(doc_file):
                print(f"Indexador disparado automaticamente por ausência de data/articles.json...")
                self.articles = run_indexing(doc_file, self.articles_json_path)
            else:
                print(f"AVISO: Arquivo docx não encontrado em {self.doc_path}. Tentando carregar JSON existente...")
                
        # Carrega o JSON
        if os.path.exists(self.articles_json_path):
            with open(self.articles_json_path, "r", encoding="utf-8") as f:
                self.articles = json.load(f)
            print(f"Sucesso: {len(self.articles)} artigos carregados na memória para RAG.")
            self._fit_tfidf()
        else:
            print("ERRO: Nenhuma base de conhecimento disponível na inicialização.")

    def _fit_tfidf(self):
        """
        Ajusta o vetorizador TF-IDF nos artigos da base de conhecimento.
        """
        if not self.articles:
            return
            
        # Unir título, categoria e conteúdo para criar o texto de índice de cada artigo
        corpus = []
        for art in self.articles:
            # Damos peso extra para o título e categoria repetindo-os no corpus
            index_text = f"{art['title']} {art['category']} {art['title']} {art['content']}"
            corpus.append(index_text.lower())
            
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """
        Busca os artigos mais similares à query usando similaridade de cosseno do TF-IDF.
        Retorna uma lista de tuplas (Artigo, score).
        """
        if not self.articles or self.tfidf_matrix is None:
            return []

        # Vectorizar a query do usuário
        query_vector = self.vectorizer.transform([query.lower()])
        
        # Calcular similaridade de cosseno contra todos os artigos
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # Obter os índices ordenados de forma decrescente
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            results.append((self.articles[idx], score))
            
        return results

    def answer_query(self, query: str, chat_history: List[Dict[str, Any]], 
                     min_confidence: float = 0.25, 
                     custom_api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Processa a pergunta, executa a busca RAG e gera a resposta via Gemini
        ou via fallback mock. Retorna um dicionário com a resposta, fontes e status.
        """
        # 1. Recuperação (Retrieval)
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
        
        # 2. Verificação de Confiança da Busca (Threshold)
        if best_score < min_confidence:
            return {
                "answer": f"Entendi que sua dúvida é sobre algo que não encontrei em nossa base de conhecimento padrão (Confiança: {best_score:.2f} < Limiar: {min_confidence:.2f}). Estou transferindo você para o suporte humano agora para te ajudar melhor!",
                "sources": [best_art],
                "confidence": best_score,
                "escalated": True,
                "reason": f"Baixa confiança na busca (Score: {best_score:.2f} < {min_confidence:.2f})"
            }

        # Filtrar as fontes que possuem alguma relevância (ex: score > 0.05) para mostrar ao usuário
        sources = [art for art, score in retrieved if score > 0.05]
        
        # 3. Escolher a chave de API do Gemini (prioriza a chave do usuário da interface, depois a do ambiente)
        api_key = custom_api_key or os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            # --- Modo Fallback / Mock Inteligente (Sem Chave API) ---
            # Extrai o "Problema" e "Solução passo a passo" do melhor artigo para formular a resposta
            fallback_answer = (
                f"**[Modo Demonstrativo - Sem Chave API]**\n\n"
                f"Aqui está o que encontrei sobre **\"{best_art['title']}\"** ({best_art['category']}):\n\n"
                f"{best_art['content']}\n\n"
                f"*Nota: Configure sua chave Gemini API nas Configurações da barra lateral para ter respostas conversacionais geradas por IA.*"
            )
            return {
                "answer": fallback_answer,
                "sources": sources,
                "confidence": best_score,
                "escalated": False,
                "mode": "fallback_mock"
            }

        # 4. Geração com LLM (RAG com Gemini)
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # Formata o contexto dos artigos relevantes
            context_text = ""
            for idx, art in enumerate(sources):
                context_text += f"Artigo [{idx + 1}]: {art['title']}\nCategoria: {art['category']}\nConteúdo:\n{art['content']}\n\n"
                
            # Formata o histórico do chat
            history_text = ""
            for msg in chat_history[-6:]: # Limita aos últimos 6 turnos para economizar tokens e focar no contexto recente
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

            response = model.generate_content(prompt)
            answer = response.text.strip()
            
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
                "mode": "gemini_generation"
            }
            
        except Exception as e:
            # Caso ocorra falha na API do Gemini (ex: chave inválida ou limite excedido)
            print(f"Erro ao chamar API do Gemini: {e}")
            fallback_answer = (
                f"**[Erro na API Gemini - Fallback Ativado]**\n\n"
                f"Encontrei uma solução direta na base de conhecimento:\n\n"
                f"{best_art['content']}\n\n"
                f"*(Erro técnico: {str(e)})*"
            )
            return {
                "answer": fallback_answer,
                "sources": sources,
                "confidence": best_score,
                "escalated": False,
                "mode": "error_fallback"
            }
