---
title: ShopFlow CX Support Agent
emoji: 🤖
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ShopFlow - Agente Inteligente de Suporte ao Cliente (RAG) & Dashboard de Métricas

Este projeto é um **Agente de Suporte de CX Inteligente** baseado em RAG (Retrieval-Augmented Generation) para a plataforma e-commerce fictícia **ShopFlow**. Ele extrai conhecimento de uma base de dados em Word, responde a perguntas dos clientes citando artigos fontes de forma contextualizada, escala chamados de baixa confiança para humanos e fornece um painel de métricas interativo em tempo real.

O projeto foi projetado para portfólio no GitHub e hospedagem fácil e gratuita no **Hugging Face Spaces** utilizando Docker.

---

## 🚀 Funcionalidades Principais

1. **Indexador Automatizado**: Carrega e trata o arquivo `ShopFlow_KnowledgeBase.docx` (60 artigos em 6 categorias), convertendo-o em uma base de dados JSON estruturada em UTF-8.
2. **Motor de Busca e Resposta (RAG)**:
   - Utiliza **TF-IDF com Similaridade de Cosseno** (via `scikit-learn`) no backend para buscar de forma rápida os artigos mais relevantes.
   - Integra-se com a API do **Google Gemini (gemini-2.5-flash)** para gerar respostas conversacionais baseadas no contexto recuperado.
   - **Modo Demonstrativo Integrado**: Funciona de forma 100% autônoma e off-line (sem API Key), exibindo as soluções diretamente do banco de dados na tela com um visual explicativo.
3. **Escalação Inteligente de Dupla Guarda**:
   - **Nível RAG**: Se a busca retornar artigos com similaridade abaixo do Limiar de Confiança ajustado, o bot transfere o cliente para um atendente de forma transparente.
   - **Nível LLM**: Se a pergunta do usuário for identificada pela IA como fora do escopo ou se o contexto for insuficiente, ela mesma dispara a ação de transferência humana.
4. **Interface do Usuário Premium (Dark Mode & Glassmorphism)**:
   - Design moderno, translúcido e responsivo.
   - Histórico do chat interativo, sugestão de perguntas rápidas, acordeão expansível para visualização detalhada do artigo fonte de cada resposta da IA.
   - Banner animado indicando status da fila humana.
5. **Painel de Métricas Operacionais**:
   - Atualizado em tempo real.
   - **Métricas Chave**: Taxa de Deflexão, Total de Tickets, Casos Resolvidos e Casos Escalados.
   - **Gráficos Interativos (Chart.js)**: Gráfico de Rosca de status e Gráfico de Barras horizontais de acessos por categoria.
   - **Log de Tickets Recentes**: Permite ao usuário clicar em "Ver Conversa" na tabela e carregar retroativamente o histórico completo daquela sessão no chat.
6. **Segurança Avançada**:
   - **Chave Oculta no Servidor**: A chave `GEMINI_API_KEY` padrão é armazenada em segredos de ambiente no Hugging Face (nunca exposta na web).
   - **Rate Limiting por IP**: Limita usuários públicos a no máximo 6 mensagens por minuto para evitar abusos na cota da sua chave.
   - **Chave de API do Usuário (Bypass)**: Opcionalmente, recrutadores podem digitar sua própria chave na barra lateral da interface. Ela fica salva apenas no navegador (`localStorage`) e desativa o limitador por IP.

---

## 🛠️ Tecnologias Utilizadas

*   **Backend**: Python, FastAPI, Uvicorn, Pydantic
*   **Processamento & NLP**: `python-docx`, `scikit-learn`, `numpy`
*   **IA Generativa**: SDK Oficial `google-generativeai` (Gemini API)
*   **Frontend**: HTML5, Vanilla CSS3 (Custom Properties, Flexbox/Grid, Glassmorphism, CSS Animations), Vanilla Javascript (ES6+, Fetch API)
*   **Visualização de Dados**: Chart.js (CDN), Lucide Icons (CDN)
*   **DevOps/Deploy**: Docker, Hugging Face Spaces

---

## 📂 Estrutura do Projeto

```text
CX Support Agent/
├── app/
│   ├── main.py          # Servidor FastAPI e rotas de API (chat, metrics, log)
│   ├── indexer.py       # Algoritmo de parseamento e limpeza do .docx
│   ├── rag.py           # Busca RAG (TF-IDF), cálculo de cosseno e geração com Gemini
│   ├── database.py      # Banco de dados leve baseado em arquivo JSON (data/db.json)
│   └── static/          # Interface Web (Frontend)
│       ├── index.html   # Estrutura HTML do Chat e Dashboard
│       ├── style.css    # Estilos CSS Modernos (Sleek Dark Mode & Transparências)
│       └── app.js       # Comportamento do cliente, API e gráficos dinâmicos
├── data/
│   ├── articles.json    # Base de conhecimento indexada (gerado dinamicamente)
│   └── db.json          # Histórico de conversas e logs persistidos (gerado dinamicamente)
├── test_system.py       # Conjunto de testes unitários locais
├── requirements.txt     # Dependências Python
├── Dockerfile           # Configuração do container Docker para Deploy
└── ShopFlow_KnowledgeBase.docx # Base de conhecimento original em Word
```

---

## 💻 Como Rodar Localmente

### Pré-requisitos
*   Python 3.10 ou superior instalado.

### Passo 1: Clone e Instalação
1. Acesse o diretório do projeto:
   ```bash
   cd "CX Support Agent"
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

### Passo 2: Executar os Testes Automatizados
Certifique-se de que os componentes principais estão funcionando rodando os testes integrados:
```bash
python test_system.py
```

### Passo 3: Rodar o Servidor
Inicie a aplicação utilizando o Uvicorn:
```bash
python -m uvicorn app.main:app --reload --port 7860
```

### Passo 4: Testar no Navegador
Acesse: [http://localhost:7860](http://localhost:7860)

---

## ☁️ Como Fazer Deploy no Hugging Face Spaces

O Hugging Face Spaces permite hospedar aplicações Docker de forma totalmente gratuita.

1.  Crie uma conta em [huggingface.co](https://huggingface.co/).
2.  No painel superior, clique em **Spaces** > **Create new Space**.
3.  Preencha as configurações:
    *   **Space Name**: `shopflow-cx-agent` (ou de sua escolha)
    *   **License**: `mit` (ou de sua escolha)
    *   **SDK**: Escolha **Docker**.
    *   **Docker Template**: Escolha **Blank**.
    *   **Space Hardware**: Escolha **CPU Basic** (Grátis).
    *   **Visibility**: Escolha **Public** (para recrutadores poderem acessar).
4.  Crie o Space.
5.  Vá em **Settings** > **Variables and Secrets** no seu Space:
    *   Adicione um **New Secret**.
    *   Nome: `GEMINI_API_KEY`
    *   Valor: *Sua chave de API do Google Gemini (obtida gratuitamente no Google AI Studio)*.
6.  Suba os arquivos deste repositório para o Space via Git ou diretamente pela interface do Hugging Face.
7.  O container será compilado e iniciado automaticamente na porta `7860`.
