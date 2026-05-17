from datetime import datetime
from pathlib import Path

import pytest

import core.cliente_nfse as cliente_nfse_module
from core.cliente_nfse import ClienteNfseNacional, EndpointsNfse, FalhaAutenticacaoError


class FakeResponse:
    def __init__(self, *, content=b"", text="", chunks=None):
        self.content = content
        self.text = text
        self._chunks = list(chunks or [])

    def iter_content(self, chunk_size=8192):
        yield from self._chunks


HTML_TOKEN = """
<html>
  <body>
    <form>
      <input name="__RequestVerificationToken" value="TOKEN-CSRF-XYZ" />
    </form>
  </body>
</html>
"""

HTML_NO_TOKEN = """
<html><body><form><input name="outro" value="x" /></form></body></html>
"""

HTML_DASHBOARD_WITH_CNPJ = """
<html>
  <body>
    <li class="dropdown perfil"><ul><li>Empresa Teste (12345678000199)</li></ul></li>
  </body>
</html>
"""

HTML_DASHBOARD_EMPTY = "<html><body><div>sem perfil</div></body></html>"

HTML_NOTAS_EMITIDAS = """
<html>
  <body>
    <table>
      <tbody>
        <tr>
          <td>01/09/2025</td>
          <td>987</td>
          <td>R$ 100,50</td>
          <td>
            <div class="list-group menu-content">
              <a href="/arquivos/nota123.xml">Download XML</a>
              <a href="/arquivos/nota123.pdf">Download DANFS-e</a>
              <a href="/arquivos/cancelar">Cancelar NFS-e</a>
              <a href="/arquivos/substituir">Substituir</a>
            </div>
          </td>
        </tr>
        <tr>
          <td>IGNORAR</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

HTML_NOTAS_RECEBIDAS = """
<html>
  <body>
    <table>
      <tbody>
        <tr>
          <td>02/09/2025</td>
          <td>123</td>
          <td>R$ 200,00</td>
          <td>
            <div class="list-group menu-content">
              <a href="/arquivos/rec123.xml">Download XML</a>
              <a href="/arquivos/rec123.pdf">Download PDF</a>
              <a href="/arquivos/rejeitar">Rejeitar</a>
              <a href="/arquivos/confirmar">Confirmar</a>
            </div>
          </td>
        </tr>
        <tr>
          <td>IGNORAR</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

HTML_SEM_TBODY_ERRO = """
<html><body><span class="field-validation-error">Erro de validação</span></body></html>
"""

HTML_SEM_TBODY_REGISTROS = """
<html><body><span class="sem-registros">Sem registros encontrados.</span></body></html>
"""

HTML_SEM_TBODY_VAZIO = "<html><body><p>vazio</p></body></html>"


def _mock_response(content_text: str) -> FakeResponse:
    return FakeResponse(content=content_text.encode("utf-8"))


def test_preparar_diretorios_cria_legado(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    cliente._preparar_diretorios()

    assert Path("downloads/xmls").exists()
    assert Path("downloads/pdfs").exists()


def test_obter_token_verificacao_sucesso_e_erros(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_TOKEN),
    )
    cliente._obter_token_verificacao()
    assert cliente._token_csrf == "TOKEN-CSRF-XYZ"

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_NO_TOKEN),
    )
    with pytest.raises(ValueError, match="token CSRF"):
        cliente._obter_token_verificacao()

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response("<html><body></body></html>"),
    )
    with pytest.raises(ValueError, match="token CSRF"):
        cliente._obter_token_verificacao()


def test_esta_autenticado_extrai_cnpj_e_false(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_DASHBOARD_WITH_CNPJ),
    )
    assert cliente.esta_autenticado() is True
    assert cliente.obter_cnpj() == "12345678000199"

    cliente_sem_perfil = ClienteNfseNacional(usuario="123", senha="456")
    monkeypatch.setattr(
        cliente_sem_perfil.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_DASHBOARD_EMPTY),
    )
    assert cliente_sem_perfil.esta_autenticado() is False


def test_obter_cnpj_prefere_extracao_e_fallback():
    cliente = ClienteNfseNacional(usuario="12.345.678/0001-99", senha="456")
    cliente._cnpj_usuario = "99999999000199"
    assert cliente.obter_cnpj() == "99999999000199"

    cliente2 = ClienteNfseNacional(usuario="12.345.678/0001-99", senha="456")
    assert cliente2.obter_cnpj() == "12345678000199"

    cliente3 = ClienteNfseNacional(usuario="abc", senha="456")
    assert cliente3.obter_cnpj() is None


def test_autenticar_usuario_senha_cobre_missings_e_falha(monkeypatch):
    cliente = ClienteNfseNacional(usuario=None, senha=None)
    monkeypatch.setattr(cliente, "_obter_token_verificacao", lambda: None)
    with pytest.raises(FalhaAutenticacaoError, match="Credenciais não fornecidas"):
        cliente.autenticar()

    cliente2 = ClienteNfseNacional(usuario="123", senha="456")
    monkeypatch.setattr(cliente2, "_obter_token_verificacao", lambda: None)
    monkeypatch.setattr(cliente2, "esta_autenticado", lambda: False)
    monkeypatch.setattr(
        cliente2.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeResponse(),
    )
    with pytest.raises(FalhaAutenticacaoError, match="Usuário ou senha incorretos"):
        cliente2.autenticar()


def test_autenticar_certificado_cobre_falha(monkeypatch):
    cliente = ClienteNfseNacional(caminho_pfx="/tmp/cert.pfx", senha_pfx="senha")
    monkeypatch.setattr(cliente, "_obter_token_verificacao", lambda: None)
    monkeypatch.setattr(cliente, "esta_autenticado", lambda: False)

    class FakeGerenciador:
        def __init__(self, caminho_pfx, senha_pfx):
            self.args = (caminho_pfx, senha_pfx)

        def __enter__(self):
            return ("/tmp/cert.pem", "/tmp/key.pem")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(cliente_nfse_module, "GerenciadorCertificadoA1", FakeGerenciador)
    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeResponse(),
    )

    with pytest.raises(FalhaAutenticacaoError, match="Certificado"):
        cliente.autenticar()


def test_emitir_nota_simples_envia_payload(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")
    chamadas = []

    def fake_enviar_requisicao(metodo, url, **kwargs):
        chamadas.append((metodo, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_enviar_requisicao)
    cliente.emitir_nota_simples({"foo": "bar"})

    assert chamadas == [("POST", EndpointsNfse.EMISSAO_DPS, {"data": {"foo": "bar"}})]


def test_listar_notas_emitidas_cobre_parametros_e_branches(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")
    chamadas = []

    def fake_enviar_requisicao(metodo, url, **kwargs):
        chamadas.append((metodo, url, kwargs))
        return _mock_response(HTML_NOTAS_EMITIDAS)

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_enviar_requisicao)

    resultado = cliente.listar_notas_emitidas("01/09/2025", "30/09/2025")

    assert chamadas[0][0] == "GET"
    assert chamadas[0][1] == EndpointsNfse.NOTAS_EMITIDAS
    assert chamadas[0][2]["params"] == {
        "busca": "",
        "datainicio": "01/09/2025",
        "datafim": "30/09/2025",
    }
    assert chamadas[0][2] == {"params": chamadas[0][2]["params"]}
    assert resultado == {
        "notas": [
            {
                "download_xml": f"{EndpointsNfse.BASE_URL}/arquivos/nota123.xml",
                "download_danfs-e": f"{EndpointsNfse.BASE_URL}/arquivos/nota123.pdf",
                "status_danfs-e": "unknown",
                "valor": "R$ 100,50",
                "data_emissao": "01/09/2025",
                "numero": "987",
            }
        ]
    }
    assert cliente._tipo_consulta == "emitidas"


def test_listar_notas_emitidas_sem_tbody_cobre_erros(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_ERRO),
    )
    resultado = cliente.listar_notas_emitidas()
    assert resultado == {"notas": [], "erro": "Erro de validação"}

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_REGISTROS),
    )
    resultado = cliente.listar_notas_emitidas()
    assert resultado == {"notas": [], "erro": "Sem registros encontrados."}

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_VAZIO),
    )
    resultado = cliente.listar_notas_emitidas()
    assert resultado == {"notas": [], "erro": "Erro desconhecido ao listar notas."}


def test_listar_notas_recebidas_cobre_branches(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_NOTAS_RECEBIDAS),
    )

    resultado = cliente.listar_notas_recebidas("01/09/2025", "30/09/2025")

    assert resultado == {
        "notas": [
            {
                "download_xml": f"{EndpointsNfse.BASE_URL}/arquivos/rec123.xml",
                "download_pdf": f"{EndpointsNfse.BASE_URL}/arquivos/rec123.pdf",
                "status_danfs-e": "gerada",
                "valor": "R$ 200,00",
                "data_emissao": "02/09/2025",
                "numero": "123",
            }
        ]
    }
    assert cliente._tipo_consulta == "recebidas"


def test_listar_notas_recebidas_sem_tbody_cobre_erros(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_ERRO),
    )
    assert cliente.listar_notas_recebidas() == {
        "notas": [],
        "erro": "Erro de validação",
    }

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_REGISTROS),
    )
    assert cliente.listar_notas_recebidas() == {
        "notas": [],
        "erro": "Sem registros encontrados.",
    }

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: _mock_response(HTML_SEM_TBODY_VAZIO),
    )
    assert cliente.listar_notas_recebidas() == {
        "notas": [],
        "erro": "Erro desconhecido ao listar notas.",
    }


def test_baixar_arquivo_cobre_datas_e_fallbacks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cliente = ClienteNfseNacional(
        usuario="123",
        senha="456",
        save_path="downloads-base",
        path_structure="{CLIENTE}/{ANO}",
        razao_social="Empresa X",
    )
    cliente.define_tipo_consulta("emitidas")

    def fake_xml(metodo, url, **kwargs):
        return FakeResponse(text="<root>\n  <item>á</item>\n</root>")

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_xml)

    caminho_xml = cliente.baixar_xml(
        "https://exemplo/nota123",
        "",
        "2025-09-01T16:24:00-03:00",
    )
    assert Path(caminho_xml).exists()
    assert Path(caminho_xml).read_text(encoding="utf-8") == "<root><item>á</item></root>"
    assert "downloads-base/Empresa X/2025/emitidas/gerada/xmls" in caminho_xml.replace("\\", "/")

    def fake_pdf(metodo, url, **kwargs):
        assert kwargs.get("stream") is True
        return FakeResponse(chunks=[b"%PDF-1.4", b"-conteudo"])

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_pdf)
    caminho_pdf = cliente.baixar_pdf(
        "https://exemplo/nota456",
        "paga",
        datetime(2025, 9, 3, 10, 11, 12),
    )
    assert Path(caminho_pdf).read_bytes() == b"%PDF-1.4-conteudo"
    assert "downloads-base/Empresa X/2025/emitidas/paga/pdfs" in caminho_pdf.replace("\\", "/")

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_xml)
    caminho_barra = cliente._baixar_arquivo(
        "https://exemplo/nota777",
        "xml",
        status="",
        data_emissao="03/09/2025",
    )
    assert Path(caminho_barra).exists()

    caminho_str = cliente._baixar_arquivo(
        "https://exemplo/nota789",
        "xml",
        status="",
        data_emissao="2025-09-03 10:11:12",
    )
    assert Path(caminho_str).exists()
    assert "2025" in caminho_str.replace("\\", "/")

    caminho_txt = cliente._baixar_arquivo(
        "https://exemplo/nota999",
        "xml",
        status="",
        data_emissao="invalido",
    )
    assert Path(caminho_txt).exists()
    assert "0000" in caminho_txt.replace("\\", "/")


def test_baixar_arquivo_retorna_vazio_em_erro(monkeypatch):
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cliente.http, "enviar_requisicao", explode)
    assert cliente.baixar_xml("https://exemplo/nota", "") == ""

