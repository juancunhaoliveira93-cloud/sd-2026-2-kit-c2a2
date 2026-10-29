"""
Armazenamento do indice vetorial - PERSISTIDO EM DISCO (TAREFA 1).

O indice fica no arquivo  <DADOS_DIR>/indice.json  e sobrevive a reinicios.
Quem escreve e o worker da fila (ou a API, so no modo de contingencia sem
Redis). A API de ingestao apenas LE: por isso, `listar()` recarrega o arquivo
sempre que ele muda no disco (outro processo pode ter gravado).

A gravacao e atomica (arquivo temporario + os.replace), entao um leitor nunca
enxerga um JSON pela metade.
"""
import json
import os
import re
import threading

from servicos.comum.embeddings import Vetorizador

DADOS_DIR = os.getenv("DADOS_DIR", "dados")
ARQUIVO_INDICE = os.path.join(DADOS_DIR, "indice.json")

_trava = threading.Lock()
_indice = []          # [{"texto": str, "origem": str, "vetor": [float]}]
_assinatura = None    # (mtime_ns, tamanho) do arquivo na ultima leitura


def _assinatura_do_arquivo():
    try:
        st = os.stat(ARQUIVO_INDICE)
        return (st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        return None


def _sincronizar():
    """Recarrega da memoria <- disco se o arquivo mudou. Chamar com a trava."""
    global _indice, _assinatura
    atual = _assinatura_do_arquivo()
    if atual == _assinatura:
        return
    if atual is None:
        _indice, _assinatura = [], None
        return
    with open(ARQUIVO_INDICE, encoding="utf-8") as f:
        _indice = json.load(f)
    _assinatura = atual


def _gravar():
    """Grava o indice em disco de forma atomica. Chamar com a trava."""
    global _assinatura
    os.makedirs(DADOS_DIR, exist_ok=True)
    temporario = ARQUIVO_INDICE + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(_indice, f, ensure_ascii=False)
    os.replace(temporario, ARQUIVO_INDICE)
    _assinatura = _assinatura_do_arquivo()


def adicionar(documentos):
    """
    Acrescenta documentos [{"texto", "origem"}] ao indice, reindexa tudo com o
    vocabulario novo (TF-IDF precisa ser reajustado) e grava em disco.

    E idempotente: o mesmo (texto, origem) enviado duas vezes nao duplica.
    Isso importa porque a fila entrega "pelo menos uma vez".
    Devolve o total de documentos no indice. Levanta ValueError (e nao grava
    nada) se algum texto nao tiver palavras, ex.: "..." ou so pontuacao.
    """
    for d in documentos:
        if not re.search(r"\w{2,}", d["texto"]):
            raise ValueError(f"documento sem texto aproveitavel: {d['texto'][:30]!r}")
    with _trava:
        _sincronizar()
        existentes = {(i["texto"], i["origem"]) for i in _indice}
        novos = []
        for d in documentos:
            chave = (d["texto"], d.get("origem", "desconhecida"))
            if chave not in existentes:
                existentes.add(chave)
                novos.append({"texto": chave[0], "origem": chave[1]})
        if not novos:
            return len(_indice)

        todos = [{"texto": i["texto"], "origem": i["origem"]} for i in _indice] + novos
        vetorizador = Vetorizador()
        vetorizador.ajustar([i["texto"] for i in todos])   # ValueError se vazio
        for item in todos:
            item["vetor"] = vetorizador.vetorizar(item["texto"])

        _indice[:] = todos
        _gravar()
        return len(_indice)


def listar():
    """Devolve todos os itens do indice (recarrega do disco se mudou)."""
    with _trava:
        _sincronizar()
        return list(_indice)


def total():
    with _trava:
        _sincronizar()
        return len(_indice)


def limpar():
    """Apaga o indice (memoria e disco). Util em testes."""
    global _indice, _assinatura
    with _trava:
        _indice, _assinatura = [], None
        if os.path.exists(ARQUIVO_INDICE):
            os.remove(ARQUIVO_INDICE)
