"""
Servico 1 - INGESTAO: recebe documentos, gera embeddings e armazena.

Fluxo:  POST /indexar  ->  publica na FILA (Redis)  ->  worker indexa
        (servicos/ingestao/worker.py)  ->  grava em disco (armazenamento.py)

Se o Redis estiver fora do ar, a API NAO quebra: indexa na hora, de forma
sincrona (degradacao elegante).

Rodar: uvicorn servicos.ingestao.app:app --port 8001
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from servicos.ingestao import armazenamento, fila

app = FastAPI(title="Ingestao - C2.A2")


class Documento(BaseModel):
    texto: str = Field(min_length=1)
    origem: str = "desconhecida"


@app.post("/indexar")
def indexar(docs: list[Documento]):
    if not docs:
        raise HTTPException(status_code=422, detail="envie ao menos um documento")
    carga = [d.model_dump() for d in docs]

    try:
        fila.publicar(carga)
    except fila.FilaIndisponivel:
        # Contingencia: sem fila, indexa direto.
        try:
            total = armazenamento.adicionar(carga)
        except ValueError as erro:
            raise HTTPException(status_code=422, detail=str(erro))
        return JSONResponse(
            status_code=200,
            content={"modo": "sincrono (fila indisponivel)", "indexados": total},
        )

    return JSONResponse(
        status_code=202,
        content={"modo": "assincrono", "enfileirados": len(carga)},
    )


@app.get("/indice")
def indice():
    """Consumido pelo servico de recuperacao."""
    itens = armazenamento.listar()
    return {
        "total": len(itens),
        "itens": [{"texto": i["texto"], "origem": i["origem"], "vetor": i["vetor"]}
                  for i in itens],
    }


@app.get("/saude")
def saude():
    return {
        "status": "ok",
        "documentos": armazenamento.total(),
        "fila": fila.estado(),
    }
