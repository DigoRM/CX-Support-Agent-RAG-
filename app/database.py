import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

class Database:
    def __init__(self, file_path: str = "data/db.json"):
        self.file_path = file_path
        # Garante que a pasta data existe
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Erro ao carregar banco de dados JSON: {e}. Inicializando novo.")
                self.data = {"conversations": {}}
        else:
            self.data = {"conversations": {}}

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar banco de dados JSON: {e}")

    def get_conversation(self, session_id: str) -> Dict[str, Any]:
        """
        Retorna ou inicializa uma sessão de conversa.
        """
        if session_id not in self.data["conversations"]:
            now = datetime.now().isoformat()
            self.data["conversations"][session_id] = {
                "session_id": session_id,
                "status": "in_progress", # in_progress, resolved, escalated
                "created_at": now,
                "updated_at": now,
                "messages": []
            }
            self._save()
        return self.data["conversations"][session_id]

    def add_message(self, session_id: str, sender: str, text: str, 
                    sources: Optional[List[Dict[str, Any]]] = None, 
                    confidence: Optional[float] = None,
                    escalated: Optional[bool] = None,
                    reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Adiciona uma mensagem ao histórico e atualiza a data de modificação.
        """
        conv = self.get_conversation(session_id)
        
        message_obj = {
            "sender": sender, # user, agent, system
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        if sources is not None:
            message_obj["sources"] = sources
        if confidence is not None:
            message_obj["confidence"] = confidence
        if escalated is not None:
            message_obj["escalated"] = escalated
        if reason is not None:
            message_obj["reason"] = reason

        conv["messages"].append(message_obj)
        conv["updated_at"] = datetime.now().isoformat()
        
        self._save()
        return conv

    def escalate_conversation(self, session_id: str, reason: str = "Solicitado pelo cliente") -> Dict[str, Any]:
        """
        Marca a conversa como escalada para atendimento humano.
        """
        conv = self.get_conversation(session_id)
        if conv["status"] != "escalated":
            conv["status"] = "escalated"
            conv["updated_at"] = datetime.now().isoformat()
            
            # Adiciona mensagem de sistema informando a escalação
            self.add_message(
                session_id=session_id,
                sender="system",
                text=f"Conversa transferida para atendimento humano. Motivo: {reason}"
            )
        return conv

    def resolve_conversation(self, session_id: str) -> Dict[str, Any]:
        """
        Marca a conversa como resolvida (defletida pela IA).
        """
        conv = self.get_conversation(session_id)
        if conv["status"] != "escalated":
            conv["status"] = "resolved"
            conv["updated_at"] = datetime.now().isoformat()
            self._save()
        return conv

    def get_metrics(self) -> Dict[str, Any]:
        """
        Calcula as métricas dinamicamente de todas as conversas salvas.
        """
        conversations = self.data["conversations"]
        total_tickets = len(conversations)
        
        escalated_tickets = 0
        resolved_tickets = 0
        in_progress_tickets = 0
        
        confidences = []
        category_counts = {}
        
        for s_id, conv in conversations.items():
            status = conv.get("status", "in_progress")
            if status == "escalated":
                escalated_tickets += 1
            elif status == "resolved":
                resolved_tickets += 1
            else:
                # Se a conversa está sem mensagens ou in_progress por padrão,
                # para o painel de suporte, consideramos que se não foi escalada até agora
                # e tem mensagens, ela pode ser tratada como resolvida de forma preliminar
                # ou mantida como in_progress. Vamos contar como in_progress
                in_progress_tickets += 1
                
            # Extrair confianças e categorias
            for msg in conv.get("messages", []):
                if msg.get("sender") == "agent":
                    conf = msg.get("confidence")
                    if conf is not None:
                        confidences.append(conf)
                        
                    # Conta as categorias dos artigos mais relevantes acessados
                    sources = msg.get("sources", [])
                    if sources:
                        # Pega a categoria da primeira fonte usada
                        cat = sources[0].get("category", "Geral")
                        category_counts[cat] = category_counts.get(cat, 0) + 1

        # Deflection Rate (Taxa de Deflexão)
        # Quantidade de tickets resolvidos (ou in_progress sem escalação) sobre o total de concluídos
        completed_tickets = resolved_tickets + escalated_tickets
        if completed_tickets > 0:
            deflection_rate = (resolved_tickets / completed_tickets) * 100
        else:
            # Se não houver tickets fechados, mas houver tickets em progresso, vamos considerá-los
            if total_tickets > 0:
                deflection_rate = ((total_tickets - escalated_tickets) / total_tickets) * 100
            else:
                deflection_rate = 100.0 # Sem tickets = 100% de eficiência inicial

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Formatar distribuição de categorias para o gráfico do frontend
        category_distribution = [{"category": cat, "count": count} for cat, count in category_counts.items()]
        # Ordenar por contagem decrescente
        category_distribution.sort(key=lambda x: x["count"], reverse=True)

        return {
            "total_tickets": total_tickets,
            "escalated_tickets": escalated_tickets,
            "resolved_tickets": resolved_tickets + in_progress_tickets, # Considera ativos sem escalação como resolvidos no painel macro
            "raw_resolved": resolved_tickets,
            "in_progress_tickets": in_progress_tickets,
            "deflection_rate": round(deflection_rate, 1),
            "average_confidence": round(avg_confidence, 2),
            "category_distribution": category_distribution
        }

    def get_recent_tickets(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retorna uma lista resumida de tickets recentes para a tabela do painel.
        """
        conversations = self.data["conversations"]
        sorted_convs = sorted(
            conversations.values(),
            key=lambda x: x.get("updated_at", ""),
            reverse=True
        )
        
        result = []
        for conv in sorted_convs[:limit]:
            # Descobrir a última pergunta do usuário como resumo do ticket
            last_query = "Sem mensagens"
            for msg in reversed(conv.get("messages", [])):
                if msg.get("sender") == "user":
                    last_query = msg.get("text", "")
                    if len(last_query) > 50:
                        last_query = last_query[:47] + "..."
                    break
                    
            result.append({
                "session_id": conv["session_id"],
                "status": conv["status"],
                "last_query": last_query,
                "updated_at": conv["updated_at"],
                "message_count": len(conv["messages"])
            })
        return result

    def reset_db(self):
        """
        Reseta o banco de dados.
        """
        self.data = {"conversations": {}}
        self._save()
        print("Banco de dados resetado.")
