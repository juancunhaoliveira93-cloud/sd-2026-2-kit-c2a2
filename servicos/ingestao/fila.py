"""
Mensageria (TAREFA 4) - lado PRODUTOR da fila de indexacao.

Usa uma lista do Redis como fila:
    fila:indexacao              mensagens aguardando
    fila:indexacao:processando  mensagens que o worker pegou e ainda nao concluiu
    fila:indexacao:erros        mensagens que falharam (dead-letter)

Formato da mensagem (JSON):
    {"documentos": [{"texto": "...", "origem": "..."}]}

A API de ingestao so chama `publicar()` e responde 202 na hora; quem de fato
vetoriza e grava e o worker (servicos/ingestao/worker.py).
"""
import json
import os

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FILA_INDEXACAO = os.getenv("FILA_INDEXACAO", "fila:indexacao")
FILA_PROCESSANDO = FILA_INDEXACAO + ":processando"
FILA_ERROS = FILA_INDEXACAO + ":erros"


class FilaIndisponivel(Exception):
    """Redis fora do ar ou inacessivel."""


def criar_cliente(socket_timeout=5):
    # connect timeout curto: se o Redis cair, a API percebe rapido e usa a contingencia
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=socket_timeout,
    )


_cliente = criar_cliente()


def publicar(documentos):
    """Coloca um lote de documentos na fila. Levanta FilaIndisponivel se falhar."""
    try:
        _cliente.rpush(FILA_INDEXACAO, json.dumps({"documentos": documentos}))
    except redis.exceptions.RedisError as erro:
        raise FilaIndisponivel(str(erro)) from erro


def estado():
    """Para o /saude: diz se a fila responde e quantas mensagens esperam."""
    try:
        return {"status": "ok", "pendentes": _cliente.llen(FILA_INDEXACAO)}
    except redis.exceptions.RedisError:
        return {"status": "indisponivel"}
