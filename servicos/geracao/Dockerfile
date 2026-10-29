# Servico de geracao - build a partir da RAIZ do repositorio (precisa de servicos/comum):
#   docker build -f servicos/geracao/Dockerfile -t rag-geracao .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependencias primeiro: a camada fica em cache enquanto requirements.txt nao mudar
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY servicos ./servicos

EXPOSE 8003
CMD ["uvicorn", "servicos.geracao.app:app", "--host", "0.0.0.0", "--port", "8003"]
