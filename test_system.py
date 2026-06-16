import os
import json
import unittest
from app.indexer import parse_docx, run_indexing
from app.database import Database
from app.rag import RAGManager

class TestCXSupportSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configura caminhos locais
        cls.doc_path = "ShopFlow_KnowledgeBase.docx"
        cls.json_path = "data/articles_test.json"
        cls.db_path = "data/db_test.json"
        
        # Limpa arquivos de teste anteriores se existirem
        if os.path.exists(cls.json_path):
            os.remove(cls.json_path)
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        # Limpa os arquivos temporários após os testes
        if os.path.exists(cls.json_path):
            os.remove(cls.json_path)
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def test_01_indexer(self):
        """Testa se o indexador faz o parseamento correto do docx e exporta os 60 artigos."""
        articles = run_indexing(self.doc_path, self.json_path)
        self.assertTrue(os.path.exists(self.json_path))
        self.assertEqual(len(articles), 60)
        
        # Valida estrutura do primeiro artigo
        first = articles[0]
        self.assertEqual(first["number"], 1)
        self.assertIn("title", first)
        self.assertIn("category", first)
        self.assertIn("content", first)
        self.assertIn("recusado", first["title"].lower() or first["content"].lower())

    def test_02_database(self):
        """Testa a criação de sessões, adição de mensagens, escalação e cálculo de métricas."""
        db = Database(self.db_path)
        session_id = "SF-TEST-99"
        
        # Inicializa
        conv = db.get_conversation(session_id)
        self.assertEqual(conv["status"], "in_progress")
        self.assertEqual(len(conv["messages"]), 0)
        
        # Adiciona mensagem do usuário
        db.add_message(session_id, "user", "Como pagar com Pix?")
        # Adiciona mensagem do agente com fonte
        sources = [{"number": 3, "title": "Pagar com Pix", "category": "Pagamentos", "content": "..."}]
        db.add_message(session_id, "agent", "Você pode pagar via Pix...", sources=sources, confidence=0.85)
        
        conv = db.get_conversation(session_id)
        self.assertEqual(len(conv["messages"]), 2)
        
        # Testa métricas antes da escalação
        metrics = db.get_metrics()
        self.assertEqual(metrics["total_tickets"], 1)
        self.assertEqual(metrics["escalated_tickets"], 0)
        self.assertEqual(metrics["deflection_rate"], 100.0)
        
        # Escala a conversa
        db.escalate_conversation(session_id, reason="Teste de Baixa Confiança")
        conv = db.get_conversation(session_id)
        self.assertEqual(conv["status"], "escalated")
        
        # Testa métricas após a escalação
        metrics = db.get_metrics()
        self.assertEqual(metrics["escalated_tickets"], 1)
        self.assertEqual(metrics["deflection_rate"], 0.0) # 1 ticket escalado de 1 total = 0% deflexão

    def test_03_rag_retrieval(self):
        """Testa se a busca RAG funciona por palavras-chave e calcula as similaridades corretas."""
        rag = RAGManager(self.doc_path, self.json_path)
        
        # Caso 1: Pergunta muito relacionada ao Artigo 1 (Pagamento recusado)
        results = rag.retrieve("pagamento recusado cartao", top_k=3)
        self.assertTrue(len(results) > 0)
        best_art, best_score = results[0]
        self.assertEqual(best_art["number"], 1)
        self.assertTrue(best_score > 0.30, f"Score esperado alto, obtido: {best_score}")
        
        # Caso 2: Pergunta sobre API de frete (Artigo relacionado a APIs)
        results_api = rag.retrieve("frete API integrar", top_k=3)
        best_art_api, best_score_api = results_api[0]
        self.assertTrue("api" in best_art_api["title"].lower() or "frete" in best_art_api["title"].lower())
        
        # Caso 3: Pergunta fora da base de conhecimento (Baixa confiança)
        results_out = rag.retrieve("como plantar flores no jardim", top_k=1)
        best_art_out, best_score_out = results_out[0]
        # Espera-se que a similaridade seja extremamente baixa
        self.assertTrue(best_score_out < 0.15, f"Score esperado baixo, obtido: {best_score_out}")

    def test_04_rag_answer_logic(self):
        """Testa se a lógica de resposta do RAG Manager detecta a baixa confiança para escalação automática."""
        rag = RAGManager(self.doc_path, self.json_path)
        
        # Pergunta de alta confiança
        res_high = rag.answer_query("Meu pagamento deu recusado", chat_history=[], min_confidence=0.25)
        self.assertFalse(res_high["escalated"])
        self.assertEqual(res_high["sources"][0]["number"], 1)
        
        # Pergunta de baixa confiança
        res_low = rag.answer_query("Qual a distância da Terra à Lua?", chat_history=[], min_confidence=0.25)
        self.assertTrue(res_low["escalated"])
        self.assertIn("suporte humano", res_low["answer"])

if __name__ == "__main__":
    unittest.main()
