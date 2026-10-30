"""
Retentativa com espera crescente (backoff exponencial) - TAREFA 3.

Complementa o circuit breaker e o tempo-limite (LLM_TIMEOUT, em comum/llm.py):

    disjuntor.chamar( com_retentativa( gerar ) )
         |                  |              |
    para de tentar     tenta de novo     cada tentativa tem
    se o LLM esta      se o erro e       tempo-limite (timeout)
    quebrado           passageiro

A retentativa fica DENTRO do disjuntor: uma pergunta que esgotou todas as
tentativas conta como UMA falha para o disjuntor.

So vale retentar erro passageiro (timeout, conexao, HTTP 429/5xx). Erro de
cliente (400, 401...) nao melhora tentando de novo, entao propaga na hora.
"""
import logging
import os
import time

import requests

log = logging.getLogger("geracao")

TENTATIVAS = int(os.getenv("LLM_TENTATIVAS", "3"))
ESPERA_INICIAL = float(os.getenv("LLM_ESPERA_INICIAL", "0.5"))   # segundos
FATOR = 2.0                                                      # 0.5s, 1s, 2s...


def erro_passageiro(erro: Exception) -> bool:
    if isinstance(erro, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(erro, requests.HTTPError) and erro.response is not None:
        codigo = erro.response.status_code
        return codigo == 429 or codigo >= 500
    return False


def com_retentativa(funcao, *args, **kwargs):
    espera = ESPERA_INICIAL
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return funcao(*args, **kwargs)
        except Exception as erro:
            ultima = tentativa == TENTATIVAS
            if ultima or not erro_passageiro(erro):
                raise
            log.warning("LLM falhou (%s); tentativa %d/%d, nova em %.1fs",
                        type(erro).__name__, tentativa, TENTATIVAS, espera)
            time.sleep(espera)
            espera *= FATOR
