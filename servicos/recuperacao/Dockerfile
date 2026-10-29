# Servico de recuperacao - build a partir da RAIZ do repositorio (precisa de servicos/comum):
#   docker build -f servicos/recuperacao/Dockerfile -t rag-recuperacao .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependencias primeiro: a camada fica em cache enquanto requirements.txt nao mudar
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY servicos ./servicos

EXPOSE 8002
CMD ["uvicorn", "servicos.recuperacao.app:app", "--host", "0.0.0.0", "--port", "8002"]
