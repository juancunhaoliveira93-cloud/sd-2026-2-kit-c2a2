"""
Testes da resiliencia do servico de geracao (sem rede, sem Redis, sem LLM real).

Rodar:  python -m unittest tests.test_geracao -v
"""
import json
import unittest
from unittest import mock

import requests

from servicos.comum.circuit_breaker import CircuitBreaker
from servicos.geracao import app as geracao
from servicos.geracao import resiliencia

TRECHOS = {"resultados": [{"texto": "O teorema CAP trata de consistencia.",
                           "origem": "teorema_cap", "score": 0.9}]}


def resposta_http(codigo):
    r = requests.Response()
    r.status_code = codigo
    return r


def conteudo(resposta):
    return json.loads(resposta.body)


class TesteRetentativa(unittest.TestCase):

    def setUp(self):
        p = mock.patch("servicos.geracao.resiliencia.time.sleep")
        p.start()
        self.addCleanup(p.stop)

    def test_recupera_apos_falhas_passageiras(self):
        f = mock.Mock(side_effect=[requests.Timeout(), requests.ConnectionError(), "ok"])
        self.assertEqual(resiliencia.com_retentativa(f), "ok")
        self.assertEqual(f.call_count, 3)

    def test_desiste_depois_do_limite(self):
        f = mock.Mock(side_effect=requests.Timeout())
        with self.assertRaises(requests.Timeout):
            resiliencia.com_retentativa(f)
        self.assertEqual(f.call_count, resiliencia.TENTATIVAS)

    def test_erro_de_cliente_nao_e_retentado(self):
        f = mock.Mock(side_effect=requests.HTTPError(response=resposta_http(401)))
        with self.assertRaises(requests.HTTPError):
            resiliencia.com_retentativa(f)
        self.assertEqual(f.call_count, 1)

    def test_erro_5xx_e_retentado(self):
        f = mock.Mock(side_effect=[requests.HTTPError(response=resposta_http(503)), "ok"])
        self.assertEqual(resiliencia.com_retentativa(f), "ok")


class TesteDisjuntorNoEndpoint(unittest.TestCase):

    def setUp(self):
        geracao.disjuntor = CircuitBreaker(limite_falhas=3, espera_segundos=60)
        geracao.disjuntor_recuperacao = CircuitBreaker(limite_falhas=3, espera_segundos=60)
        for alvo, valor in [
            ("servicos.geracao.app.requests.post",
             mock.Mock(return_value=mock.Mock(json=lambda: TRECHOS,
                                              raise_for_status=lambda: None))),
            ("servicos.geracao.resiliencia.time.sleep", mock.Mock()),
        ]:
            p = mock.patch(alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        self.pergunta = geracao.Pergunta(pergunta="o que diz o teorema CAP?")

    def test_caminho_feliz(self):
        with mock.patch("servicos.geracao.app.gerar", return_value="resposta X"):
            r = geracao.perguntar(self.pergunta)
        self.assertEqual(r["resposta"], "resposta X")
        self.assertEqual(r["fontes"], ["teorema_cap"])

    def test_disjuntor_abre_e_devolve_503(self):
        with mock.patch("servicos.geracao.app.gerar",
                        side_effect=requests.ConnectionError()) as llm:
            # 3 perguntas falham (cada uma esgota as retentativas) -> 502
            for _ in range(3):
                self.assertEqual(geracao.perguntar(self.pergunta).status_code, 502)
            self.assertEqual(geracao.disjuntor.estado, "aberto")
            chamadas_antes = llm.call_count

            # agora o circuito esta aberto: 503 imediato, SEM tocar no LLM
            r = geracao.perguntar(self.pergunta)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(llm.call_count, chamadas_antes)
            self.assertEqual(conteudo(r)["contexto"],
                             ["O teorema CAP trata de consistencia."])

    def test_sem_contexto_nao_chama_llm(self):
        geracao.requests.post.return_value.json = lambda: {"resultados": []}
        with mock.patch("servicos.geracao.app.gerar") as llm:
            r = geracao.perguntar(self.pergunta)
        llm.assert_not_called()
        self.assertEqual(r["fontes"], [])

    def test_recuperacao_fora_do_ar_devolve_503(self):
        geracao.requests.post.side_effect = requests.ConnectionError()
        self.assertEqual(geracao.perguntar(self.pergunta).status_code, 503)

    def test_disjuntor_da_recuperacao_abre_e_recusa_na_hora(self):
        geracao.requests.post.side_effect = requests.ConnectionError()
        for _ in range(3):
            r = geracao.perguntar(self.pergunta)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(conteudo(r)["erro"], "servico de recuperacao indisponivel")
        self.assertEqual(geracao.disjuntor_recuperacao.estado, "aberto")
        chamadas_antes = geracao.requests.post.call_count

        # circuito aberto: 503 imediato, SEM tentar a recuperacao, com Retry-After
        r = geracao.perguntar(self.pergunta)
        self.assertEqual(r.status_code, 503)
        self.assertIn("circuit breaker aberto", conteudo(r)["erro"])
        self.assertEqual(conteudo(r)["disjuntor"], "aberto")
        self.assertIn("retry-after", r.headers)
        self.assertEqual(geracao.requests.post.call_count, chamadas_antes)

    def test_disjuntores_sao_independentes(self):
        geracao.requests.post.side_effect = requests.ConnectionError()
        for _ in range(3):
            geracao.perguntar(self.pergunta)
        self.assertEqual(geracao.disjuntor_recuperacao.estado, "aberto")
        self.assertEqual(geracao.disjuntor.estado, "fechado")   # o do LLM nao foi afetado

    def test_recuperacao_volta_e_o_disjuntor_fecha(self):
        geracao.disjuntor_recuperacao = CircuitBreaker(limite_falhas=3, espera_segundos=0)
        geracao.requests.post.side_effect = requests.ConnectionError()
        for _ in range(3):
            geracao.perguntar(self.pergunta)
        self.assertEqual(geracao.disjuntor_recuperacao.estado, "aberto")

        geracao.requests.post.side_effect = None            # recuperacao voltou
        with mock.patch("servicos.geracao.app.gerar", return_value="ok"):
            r = geracao.perguntar(self.pergunta)             # meio-aberto -> sucesso
        self.assertEqual(r["resposta"], "ok")
        self.assertEqual(geracao.disjuntor_recuperacao.estado, "fechado")


if __name__ == "__main__":
    unittest.main()
