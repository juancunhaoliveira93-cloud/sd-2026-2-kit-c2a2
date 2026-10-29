# Servico de ingestao - build a partir da RAIZ do repositorio (precisa de servicos/comum):
#   docker build -f servicos/ingestao/Dockerfile -t rag-ingestao .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependencias primeiro: a camada fica em cache enquanto requirements.txt nao mudar
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY servicos ./servicos

EXPOSE 8001
CMD ["uvicorn", "servicos.ingestao.app:app", "--host", "0.0.0.0", "--port", "8001"]
