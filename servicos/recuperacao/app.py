"""
Servico 2 - RECUPERACAO: dada uma pergunta, acha os trechos mais relevantes.

TAREFA 2: busca por similaridade (cosseno) sobre o indice da ingestao.

Como funciona:
  1. busca o indice no servico de ingestao (GET /indice);
  2. vetoriza a pergunta com o MESMO vocabulario do indice;
  3. calcula a similaridade com cada trecho e devolve os top_k.

Rodar: uvicorn servicos.recuperacao.app:app --port 8002
"""
import hashlib
import os

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from servicos.comum.embeddings import Vetorizador, similaridade

app = FastAPI(title="Recuperacao - C2.A2")
URL_INGESTAO = os.getenv("URL_INGESTAO", "http://localhost:8001")
TIMEOUT_INGESTAO = float(os.getenv("TIMEOUT_INGESTAO", "10"))
# trechos com similaridade <= este valor sao descartados (nao tem nada a ver com a pergunta)
SCORE_MINIMO = float(os.getenv("SCORE_MINIMO", "0.0"))


class Consulta(BaseModel):
    pergunta: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


# Cache do vetorizador: so reajusta quando o conjunto de textos muda.
_cache = {"assinatura": None, "vetorizador": None}


def _vetorizador_para(textos):
    """
    O TF-IDF e deterministico: ajustado sobre os MESMOS textos da ingestao,
    ele reproduz o mesmo vocabulario, e a pergunta cai no mesmo espaco dos
    vetores que ja estao no indice.
    """
    assinatura = hashlib.md5("\n".join(textos).encode("utf-8")).hexdigest()
    if _cache["assinatura"] != assinatura:
        vetorizador = Vetorizador()
        vetorizador.ajustar(textos)
        _cache["assinatura"], _cache["vetorizador"] = assinatura, vetorizador
    return _cache["vetorizador"]


@app.post("/buscar")
def buscar(consulta: Consulta):
    """Devolve os top_k trechos mais parecidos com a pergunta, do mais para o menos relevante."""
    try:
        r = requests.get(f"{URL_INGESTAO}/indice", timeout=TIMEOUT_INGESTAO)
        r.raise_for_status()
    except requests.RequestException as erro:
        raise HTTPException(status_code=503,
                            detail=f"servico de ingestao indisponivel: {erro}")
    itens = r.json()["itens"]
    if not itens:
        return {"resultados": []}

    vetorizador = _vetorizador_para([i["texto"] for i in itens])
    vetor_pergunta = vetorizador.vetorizar(consulta.pergunta)

    pontuados = []
    for item in itens:
        vetor_item = item["vetor"]
        if len(vetor_item) != len(vetor_pergunta):      # seguranca: espaco diferente
            vetor_item = vetorizador.vetorizar(item["texto"])
        pontuados.append((similaridade(vetor_pergunta, vetor_item), item))

    pontuados.sort(key=lambda par: par[0], reverse=True)
    resultados = [
        {"texto": item["texto"], "origem": item["origem"], "score": round(score, 4)}
        for score, item in pontuados[:consulta.top_k]
        if score > SCORE_MINIMO
    ]
    return {"resultados": resultados}


@app.get("/saude")
def saude():
    return {"status": "ok"}
