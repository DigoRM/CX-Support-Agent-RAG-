import docx
import re
import os
import json

def parse_docx(file_path: str):
    """
    Realiza o parseamento do arquivo Word (.docx) da base de conhecimento
    e extrai os artigos de forma estruturada.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo da base de conhecimento não encontrado em: {file_path}")
        
    doc = docx.Document(file_path)
    articles = []
    
    current_category = "Geral"
    current_article = None
    
    # Regex para identificar categorias e artigos
    category_pattern = re.compile(r"^CATEGORIA\s+(\d+)\s*:\s*(.*)$", re.IGNORECASE)
    article_pattern = re.compile(r"^Artigo\s+(\d+)\s*[-–—]\s*(.*)$", re.IGNORECASE)
    
    content_lines = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
            
        # Tenta detectar categoria
        cat_match = category_pattern.match(text)
        if cat_match:
            # Substitui caracteres especiais quebrados se houver (ex: encoding do docx)
            cat_name = cat_match.group(2).strip()
            cat_name = cat_name.replace("COBRANAS", "COBRANÇAS")
            cat_name = cat_name.replace("INTEGRAES", "INTEGRAÇÕES")
            cat_name = cat_name.replace("CONFIGURAO", "CONFIGURAÇÃO")
            cat_name = cat_name.replace("DEVOLUES", "DEVOLUÇÕES")
            current_category = f"Categoria {cat_match.group(1)}: {cat_name}"
            continue
            
        # Tenta detectar artigo
        art_match = article_pattern.match(text)
        if art_match:
            # Salva o artigo anterior se existir
            if current_article:
                current_article["content"] = "\n".join(content_lines).strip()
                articles.append(current_article)
            
            title = art_match.group(2).strip()
            title = title.replace("Transao", "Transação")
            title = title.replace("no", "não")
            title = title.replace("confirmao", "confirmação")
            
            current_article = {
                "number": int(art_match.group(1)),
                "title": title,
                "category": current_category,
                "content": ""
            }
            content_lines = []
        else:
            if current_article:
                # Corrige problemas comuns de codificação de texto na leitura
                clean_text = text.replace("Transao", "Transação")
                clean_text = clean_text.replace("no", "não")
                clean_text = clean_text.replace("confirmao", "confirmação")
                clean_text = clean_text.replace("Soluo", "Solução")
                clean_text = clean_text.replace("carto", "cartão")
                clean_text = clean_text.replace("nmero", "número")
                clean_text = clean_text.replace("mtodo", "método")
                clean_text = clean_text.replace("aceitos", "aceitos")
                clean_text = clean_text.replace("Poltica", "Política")
                clean_text = clean_text.replace("cobrana", "cobrança")
                clean_text = clean_text.replace("cartes", "cartões")
                clean_text = clean_text.replace("automatizao", "automatização")
                clean_text = clean_text.replace("configurao", "configuração")
                clean_text = clean_text.replace("usurio", "usuário")
                clean_text = clean_text.replace("integrao", "integração")
                clean_text = clean_text.replace("padro", "padrão")
                clean_text = clean_text.replace("indisponvel", "indisponível",)
                clean_text = clean_text.replace("teis", "úteis")
                clean_text = clean_text.replace("–", "—") # traço longo ou caracteres desconhecidos
                
                content_lines.append(clean_text)
                
    # Salva o último artigo
    if current_article:
        current_article["content"] = "\n".join(content_lines).strip()
        articles.append(current_article)
        
    return articles

def run_indexing(doc_path: str, output_path: str):
    """
    Lê a base de conhecimento e exporta os dados processados para um arquivo JSON.
    """
    print(f"Iniciando indexação de {doc_path}...")
    articles = parse_docx(doc_path)
    
    # Garante que a pasta destino existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
        
    print(f"Indexação concluída com sucesso! {len(articles)} artigos salvos em {output_path}.")
    return articles

if __name__ == "__main__":
    # Caminhos para execução de teste direto
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_doc = os.path.join(base_dir, "ShopFlow_KnowledgeBase.docx")
    default_output = os.path.join(base_dir, "data", "articles.json")
    
    # Se rodando da raiz do projeto
    if not os.path.exists(default_doc):
        default_doc = os.path.join(os.getcwd(), "ShopFlow_KnowledgeBase.docx")
        default_output = os.path.join(os.getcwd(), "data", "articles.json")
        
    run_indexing(default_doc, default_output)
