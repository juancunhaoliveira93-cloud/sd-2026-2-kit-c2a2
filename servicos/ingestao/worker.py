"""
Mensageria (TAREFA 4) - lado CONSUMIDOR: worker da fila de indexacao.

Pega mensagens de `fila:indexacao`, vetoriza e grava o indice em disco.

Garantias:
  - Entrega "pelo menos uma vez": a mensagem e MOVIDA para `...:processando`
    (BLMOVE) e so e apagada de la depois de indexada. Se o worker morrer no
    meio, ao reiniciar ele devolve essas mensagens para a fila.
  - Mensagem invalida nao trava a fila: vai para `...:erros` (dead-letter).
  - Redis caiu? O worker espera e tenta de novo, sem encerrar.

Rodar: python -m servicos.ingestao.worker
"""
import json
import logging
import time

import redis

from servicos.ingestao import armazenamento
from servicos.ingestao.fila import (FILA_ERROS, FILA_INDEXACAO,
                                    FILA_PROCESSANDO, criar_cliente)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [worker] %(levelname)s %(message)s")
log = logging.getLogger("worker")

ESPERA_BLOQUEIO = 5     # segundos bloqueado esperando mensagem
ESPERA_RECONEXAO = 2    # segundos antes de tentar o Redis de novo


def processar(carga: str):
    """Indexa uma mensagem. Levanta excecao se ela for invalida."""
    mensagem = json.loads(carga)
    total = armazenamento.adicionar(mensagem["documentos"])
    log.info("indexados %d documento(s); indice agora tem %d",
             len(mensagem["documentos"]), total)


def devolver_pendentes(r):
    """Mensagens que ficaram em 'processando' (worker anterior morreu) voltam pra fila."""
    devolvidas = 0
    while r.lmove(FILA_PROCESSANDO, FILA_INDEXACAO, "LEFT", "LEFT"):
        devolvidas += 1
    if devolvidas:
        log.warning("%d mensagem(ns) pendente(s) devolvida(s) a fila", devolvidas)


def principal():
    # timeout do socket maior que o do bloqueio, senao o BLMOVE estoura sozinho
    r = criar_cliente(socket_timeout=ESPERA_BLOQUEIO + 5)
    log.info("worker iniciado; escutando '%s'", FILA_INDEXACAO)

    pendentes_tratados = False
    while True:
        try:
            if not pendentes_tratados:
                devolver_pendentes(r)
                pendentes_tratados = True

            carga = r.blmove(FILA_INDEXACAO, FILA_PROCESSANDO,
                             ESPERA_BLOQUEIO, "LEFT", "RIGHT")
            if carga is None:          # estourou o tempo sem mensagem: volta a esperar
                continue

            try:
                processar(carga)
            except Exception as erro:  # mensagem ruim: nao pode derrubar o worker
                log.error("falha ao processar (%s); enviada para '%s'", erro, FILA_ERROS)
                r.lpush(FILA_ERROS, carga)
            r.lrem(FILA_PROCESSANDO, 1, carga)

        except redis.exceptions.RedisError as erro:
            log.warning("Redis indisponivel (%s); nova tentativa em %ds",
                        erro, ESPERA_RECONEXAO)
            pendentes_tratados = False
            time.sleep(ESPERA_RECONEXAO)


if __name__ == "__main__":
    principal()
