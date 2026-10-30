"""
Servico 3 - GERACAO: monta o prompt com o contexto e chama o LLM.

TAREFA 3: a chamada ao LLM e protegida por TRES mecanismos:
  - tempo-limite  : cada tentativa expira (LLM_TIMEOUT, em comum/llm.py)
  - retentativa   : erros passageiros sao repetidos com backoff (resiliencia.py)
  - circuit breaker: depois de falhas seguidas, para de chamar o LLM por um tempo

A chamada ao servico de RECUPERACAO tem seu proprio circuit breaker (independente
do do LLM): se a recuperacao cair, o circuito abre e as proximas perguntas
recebem 503 na hora, sem esperar timeout.

Se o LLM estiver fora, o servico NAO quebra: responde 502/503 com mensagem
clara e devolve os trechos recuperados, para o cliente ao menos ver as fontes.

Rodar: uvicorn servicos.geracao.app:app --port 8003
"""
import logging
import os

import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto
from servicos.comum.llm import gerar
from servicos.geracao.resiliencia import com_retentativa

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("geracao")

app = FastAPI(title="Geracao - C2.A2")
URL_RECUPERACAO = os.getenv("URL_RECUPERACAO", "http://localhost:8002")
TIMEOUT_RECUPERACAO = float(os.getenv("TIMEOUT_RECUPERACAO", "10"))
TOP_K = int(os.getenv("TOP_K", "3"))

ESPERA_DISJUNTOR = int(os.getenv("DISJUNTOR_ESPERA", "20"))
disjuntor = CircuitBreaker(
    limite_falhas=int(os.getenv("DISJUNTOR_LIMITE", "3")),
    espera_segundos=ESPERA_DISJUNTOR,
)


ESPERA_DISJUNTOR_REC = int(os.getenv("DISJUNTOR_REC_ESPERA", "10"))
disjuntor_recuperacao = CircuitBreaker(
    limite_falhas=int(os.getenv("DISJUNTOR_REC_LIMITE", "3")),
    espera_segundos=ESPERA_DISJUNTOR_REC,
)


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1)


def _erro(status, mensagem, contexto, fontes, headers=None, estado=None):
    return JSONResponse(
        status_code=status,
        content={"erro": mensagem, "disjuntor": estado or disjuntor.estado,
                 "contexto": contexto, "fontes": fontes},
        headers=headers,
    )


def _buscar_trechos(pergunta):
    """Chamada REST ao servico de recuperacao (protegida pelo disjuntor_recuperacao)."""
    r = requests.post(f"{URL_RECUPERACAO}/buscar",
                      json={"pergunta": pergunta, "top_k": TOP_K},
                      timeout=TIMEOUT_RECUPERACAO)
    r.raise_for_status()
    return r.json()["resultados"]


@app.post("/perguntar")
def perguntar(p: Pergunta):
    # 1) RECUPERACAO: trechos mais relevantes (chamada REST ao servico 2)
    try:
        resultados = disjuntor_recuperacao.chamar(_buscar_trechos, p.pergunta)
    except CircuitoAberto:
        return _erro(503, "servico de recuperacao temporariamente indisponivel "
                          "(circuit breaker aberto); tente novamente em instantes",
                     [], [], headers={"Retry-After": str(ESPERA_DISJUNTOR_REC)},
                     estado=disjuntor_recuperacao.estado)
    except (requests.RequestException, KeyError, ValueError) as erro:
        log.error("recuperacao indisponivel: %s", erro)
        return _erro(503, "servico de recuperacao indisponivel", [], [],
                     estado=disjuntor_recuperacao.estado)

    contexto = [t["texto"] for t in resultados]
    fontes = sorted({t["origem"] for t in resultados})

    # Nada relevante nos documentos: nao gasta chamada de LLM nem inventa resposta.
    if not contexto:
        return {"pergunta": p.pergunta,
                "resposta": "Nao encontrei essa informacao nos documentos indexados.",
                "contexto": [], "fontes": []}

    # 2) GERACAO: LLM protegido por circuit breaker + retentativa + timeout
    try:
        resposta = disjuntor.chamar(com_retentativa, gerar, p.pergunta, contexto)
    except CircuitoAberto:
        return _erro(503, "LLM temporariamente indisponivel (circuit breaker aberto); "
                          "tente novamente em instantes", contexto, fontes,
                     headers={"Retry-After": str(ESPERA_DISJUNTOR)})
    except Exception as erro:
        log.error("LLM falhou apos retentativas: %s", erro)
        return _erro(502, f"falha ao consultar o LLM: {type(erro).__name__}",
                     contexto, fontes)

    return {"pergunta": p.pergunta, "resposta": resposta,
            "contexto": contexto, "fontes": fontes}


@app.get("/saude")
def saude():
    return {"status": "ok", "disjuntor": disjuntor.estado,
            "disjuntor_recuperacao": disjuntor_recuperacao.estado}
