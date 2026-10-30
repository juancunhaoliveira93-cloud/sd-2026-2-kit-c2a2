"""
Teste de ponta a ponta (TAREFA 5): documentos entram -> pergunta entra -> resposta
fundamentada nos documentos sai. Precisa do sistema rodando (docker compose up).

Uso:
    python scripts/teste_e2e.py
    URL_INGESTAO=http://localhost:8001 URL_GERACAO=http://localhost:8003 python scripts/teste_e2e.py
"""
import os
import sys
import time

import requests

INGESTAO = os.getenv("URL_INGESTAO", "http://localhost:8001")
GERACAO = os.getenv("URL_GERACAO", "http://localhost:8003")

DOCS = [
    {"origem": "teorema_cap",
     "texto": "O teorema CAP afirma que, diante de uma particao de rede, um sistema "
              "distribuido precisa escolher entre consistencia e disponibilidade."},
    {"origem": "consenso_raft",
     "texto": "Raft e um algoritmo de consenso baseado em eleicao de lider e log "
              "replicado. Uma operacao e confirmada quando a maioria dos nos registra."},
    {"origem": "sistemas_distribuidos",
     "texto": "Um sistema distribuido e um conjunto de computadores independentes que "
              "cooperam. O principal desafio e a falha parcial."},
]
PERGUNTAS = [
    ("o que diz o teorema CAP?", "teorema_cap"),
    ("como o Raft confirma uma operacao?", "consenso_raft"),
]


def passo(texto):
    print(f"\n== {texto}")


def exigir(condicao, mensagem):
    if not condicao:
        print(f"FALHOU: {mensagem}")
        sys.exit(1)
    print(f"ok: {mensagem}")


passo("1. servicos no ar")
for nome, url in [("ingestao", INGESTAO), ("geracao", GERACAO)]:
    r = requests.get(f"{url}/saude", timeout=5)
    exigir(r.status_code == 200, f"{nome} responde /saude")

passo("2. indexar documentos (passa pela fila)")
r = requests.post(f"{INGESTAO}/indexar", json=DOCS, timeout=10)
exigir(r.status_code in (200, 202), f"/indexar aceitou os documentos ({r.status_code} {r.json()})")

passo("3. aguardar o worker indexar")
limite = time.time() + 20
while time.time() < limite:
    if requests.get(f"{INGESTAO}/saude", timeout=5).json()["documentos"] >= len(DOCS):
        break
    time.sleep(0.5)
exigir(requests.get(f"{INGESTAO}/saude", timeout=5).json()["documentos"] >= len(DOCS),
       "indice contem os documentos enviados")

passo("4. perguntar")
for pergunta, fonte_esperada in PERGUNTAS:
    r = requests.post(f"{GERACAO}/perguntar", json={"pergunta": pergunta}, timeout=60)
    exigir(r.status_code == 200, f"'{pergunta}' -> HTTP 200")
    corpo = r.json()
    exigir(bool(corpo["resposta"].strip()), "resposta nao vazia")
    exigir(fonte_esperada in corpo["fontes"],
           f"resposta fundamentada em '{fonte_esperada}' (fontes: {corpo['fontes']})")

print("\nTUDO OK - fluxo de ponta a ponta funcionando.")
