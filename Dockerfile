FROM python:3.11-slim

# Evitar gravação de arquivos .pyc e buffer de saída do Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Instalar dependências do sistema necessárias para compilação se houver
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Criar diretório para dados persistentes do banco local
RUN mkdir -p /code/data && chmod 777 /code/data

# Copiar código-fonte da aplicação
COPY ./app /code/app
COPY ./ShopFlow_KnowledgeBase.docx /code/ShopFlow_KnowledgeBase.docx

# Hugging Face Spaces usa a porta 7860
EXPOSE 7860

# Comando para iniciar o servidor web
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
