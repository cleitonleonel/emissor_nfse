import requests
import pytest

from core.cliente_http import ClienteHttp


class DummyResponse:
    def __init__(self) -> None:
        self.raise_called = False

    def raise_for_status(self) -> None:
        self.raise_called = True


def test_enviar_requisicao_retorna_resposta(monkeypatch):
    cliente = ClienteHttp()
    resposta = DummyResponse()
    chamadas = {}

    def fake_request(metodo, url, **kwargs):
        chamadas["metodo"] = metodo
        chamadas["url"] = url
        chamadas["kwargs"] = kwargs
        return resposta

    monkeypatch.setattr(cliente.sessao, "request", fake_request)

    retorno = cliente.enviar_requisicao("GET", "https://example.com", timeout=10)

    assert retorno is resposta
    assert resposta.raise_called is True
    assert chamadas == {
        "metodo": "GET",
        "url": "https://example.com",
        "kwargs": {"timeout": 10},
    }


def test_enviar_requisicao_loga_erro_e_relanca(monkeypatch, caplog):
    cliente = ClienteHttp()

    def fake_request(*args, **kwargs):
        raise requests.RequestException("falha de rede")

    monkeypatch.setattr(cliente.sessao, "request", fake_request)

    with caplog.at_level("ERROR"):
        with pytest.raises(requests.RequestException):
            cliente.enviar_requisicao("POST", "https://example.com/login")

    assert "Erro na requisição POST https://example.com/login" in caplog.text

