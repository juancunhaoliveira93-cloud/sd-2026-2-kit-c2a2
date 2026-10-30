# TAREFAS - Trabalho C2.A2 (RAG Distribuido)

## Nucleo obrigatorio

- [x] **1. Persistir o indice** - `servicos/ingestao/app.py`
      O indice hoje some ao reiniciar. Guarde em arquivo ou banco vetorial.
      Feito (Carine): indice em `dados/indice.json`, gravacao atomica, sobrevive a reinicio.

- [x] **2. Busca por similaridade** - `servicos/recuperacao/app.py`
      Vetorizar a pergunta, comparar com cada documento e devolver os top_k. (Aula 9/10)
      Feito (Gustavo): similaridade do cosseno, top_k, origem e score.

- [x] **3. Circuit breaker no LLM** - `servicos/geracao/app.py`
      Envolver a chamada `gerar(...)` com `disjuntor.chamar(...)` e devolver 503
      quando o circuito estiver aberto. (Aula 11)
      Feito (Juan): disjuntor + retentativa + timeout no LLM; 503 com Retry-After.
      Extra: segundo disjuntor, independente, na chamada a recuperacao.

- [x] **4. Mensageria** - novo worker + `docker-compose.yml`
      Ao menos UMA etapa do fluxo deve passar por fila, e nao por chamada direta. (Aula 8)
      Feito (Lucas, Victor): fila Redis + worker (`fila.py`, `worker.py`) e servico no compose.

- [x] **5. Fluxo completo** - de ponta a ponta
      Pergunta entra em /perguntar e sai uma resposta fundamentada nos documentos.
      Feito (Juan): `scripts/teste_e2e.py` valida o fluxo completo.

- [x] **6. README com diagrama** da arquitetura dos tres servicos.
      Feito (Victor): README com diagrama Mermaid.

## Extensoes opcionais

- [ ] Reordenar os trechos por relevancia (reranking)
- [x] Citar quais documentos embasaram a resposta (campo `fontes`)
- [ ] Avaliacao automatica simples da qualidade da resposta
- [ ] Trocar TF-IDF por embeddings de verdade (sentence-transformers)

## Antes de entregar

- [x] Desligue a internet: o modo simulado do LLM mantem o sistema de pe?
- [x] Derrube o servico de recuperacao: o disjuntor abre como esperado?
- [x] A chave da API esta FORA do codigo (em variavel de ambiente)?
