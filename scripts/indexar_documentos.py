"""
Envia os arquivos .txt da pasta documentos/ para o servico de ingestao.

Uso:
    python scripts/indexar_documentos.py
    python scripts/indexar_documentos.py minha_pasta http://localhost:8001

Cada arquivo vira um documento; o nome do arquivo (sem .txt) e a "origem".
"""
import os
import sys

import requests

pasta = sys.argv[1] if len(sys.argv) > 1 else "documentos"
url = sys.argv[2] if len(sys.argv) > 2 else os.getenv("URL_INGESTAO", "http://localhost:8001")

docs = []
for nome in sorted(os.listdir(pasta)):
    if nome.endswith(".txt"):
        with open(os.path.join(pasta, nome), encoding="utf-8") as f:
            texto = f.read().strip()
        if texto:
            docs.append({"texto": texto, "origem": nome[:-4]})

if not docs:
    sys.exit(f"nenhum .txt encontrado em '{pasta}'")

resposta = requests.post(f"{url}/indexar", json=docs, timeout=10)
resposta.raise_for_status()
print(f"{len(docs)} documento(s) enviado(s) -> {resposta.status_code} {resposta.json()}")
