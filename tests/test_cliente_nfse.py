from pathlib import Path

import core.cliente_nfse as cliente_nfse_module
from core.cliente_nfse import ClienteNfseNacional, EndpointsNfse


class FakeResponse:
    def __init__(self, *, content=b"", text="", chunks=None):
        self.content = content
        self.text = text
        self._chunks = list(chunks or [])

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


HTML_LOGIN_AUTENTICADO = """
<html>
  <body>
    <ul>
      <li class="dropdown perfil">
        <ul>
          <li>Usuário Teste</li>
        </ul>
      </li>
    </ul>
  </body>
</html>
"""

HTML_NOTAS = """
<html>
  <body>
    <table>
      <tbody>
        <tr>
          <td>
            <div class="list-group menu-content">
              <a href="/arquivos/nota123.xml">Download XML</a>
              <a href="/arquivos/nota123.pdf">Download DANFS-e</a>
              <a href="/arquivos/cancelar">Cancelar NFS-e</a>
              <a href="/arquivos/substituir">Substituir</a>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

HTML_SEM_REGISTROS = """
<html>
  <body>
    <span class="sem-registros">Sem registros encontrados.</span>
  </body>
</html>
"""

HTML_DASHBOARD = """
<html>
  <body>
    <li class="dropdown perfil">
      <ul>
        <li>Empresa Exemplo</li>
      </ul>
    </li>
  </body>
</html>
"""


def _isolar_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path





def test_autenticar_via_usuario_e_senha(tmp_path, monkeypatch):
    _isolar_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ClienteNfseNacional,
        "_obter_token_verificacao",
        lambda self: setattr(self, "_token_csrf", "TOKEN-CSRF"),
    )
    monkeypatch.setattr(ClienteNfseNacional, "esta_autenticado", lambda self: True)

    cliente = ClienteNfseNacional(usuario="12345678000199", senha="senha-secreta")
    chamadas = []

    def fake_enviar_requisicao(metodo, url, **kwargs):
        chamadas.append((metodo, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_enviar_requisicao)

    assert cliente.autenticar() is True
    assert chamadas[0][0] == "POST"
    assert chamadas[0][1] == EndpointsNfse.LOGIN
    assert chamadas[0][2]["headers"] == {
        "origin": EndpointsNfse.BASE_URL,
        "referer": EndpointsNfse.LOGIN,
    }
    assert chamadas[0][2]["data"] == {
        "Inscricao": "12345678000199",
        "Senha": "senha-secreta",
        "__RequestVerificationToken": "TOKEN-CSRF",
    }


def test_autenticar_via_certificado(tmp_path, monkeypatch):
    _isolar_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ClienteNfseNacional,
        "_obter_token_verificacao",
        lambda self: setattr(self, "_token_csrf", "TOKEN-CSRF"),
    )
    monkeypatch.setattr(ClienteNfseNacional, "esta_autenticado", lambda self: True)

    captured = {}

    class FakeGerenciadorCertificadoA1:
        def __init__(self, caminho_pfx, senha):
            captured["caminho_pfx"] = caminho_pfx
            captured["senha_pfx"] = senha

        def __enter__(self):
            return ("/tmp/cert.pem", "/tmp/key.pem")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(
        cliente_nfse_module,
        "GerenciadorCertificadoA1",
        FakeGerenciadorCertificadoA1,
    )

    cliente = ClienteNfseNacional(caminho_pfx="/caminho/certificado.pfx", senha_pfx="senha-cert")
    chamadas = []

    def fake_enviar_requisicao(metodo, url, **kwargs):
        chamadas.append((metodo, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_enviar_requisicao)

    assert cliente.autenticar() is True
    assert captured == {
        "caminho_pfx": "/caminho/certificado.pfx",
        "senha_pfx": "senha-cert",
    }
    assert chamadas[0][0] == "POST"
    assert chamadas[0][1] == EndpointsNfse.LOGIN_CERTIFICADO
    assert chamadas[0][2]["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")


def test_esta_autenticado_detecta_usuario_logado(tmp_path, monkeypatch):
    _isolar_cwd(tmp_path, monkeypatch)
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeResponse(content=HTML_DASHBOARD.encode("utf-8")),
    )

    assert cliente.esta_autenticado() is True


def test_listar_notas_emitidas_parseia_links(tmp_path, monkeypatch):
    _isolar_cwd(tmp_path, monkeypatch)
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeResponse(content=HTML_NOTAS.encode("utf-8")),
    )

    resultado = cliente.listar_notas_emitidas("01/01/2026", "31/01/2026")

    assert "erro" not in resultado
    assert resultado["notas"] == [
        {
            "download_xml": f"{EndpointsNfse.BASE_URL}/arquivos/nota123.xml",
            "download_danfs-e": f"{EndpointsNfse.BASE_URL}/arquivos/nota123.pdf",
            "status_danfs-e": "unknown",
            "valor": "0,00",
            "data_emissao": "",
            "numero": ""
        }
    ]


def test_listar_notas_emitidas_retorna_erro_quando_sem_tbody(tmp_path, monkeypatch):
    _isolar_cwd(tmp_path, monkeypatch)
    cliente = ClienteNfseNacional(usuario="123", senha="456")

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeResponse(content=HTML_SEM_REGISTROS.encode("utf-8")),
    )

    resultado = cliente.listar_notas_emitidas("01/01/2026", "31/01/2026")

    assert resultado == {
        "notas": [],
        "erro": "Sem registros encontrados.",
    }


def test_baixar_xml_e_pdf_salva_arquivos(tmp_path, monkeypatch):
    isolated_cwd = _isolar_cwd(tmp_path, monkeypatch)
    cliente = ClienteNfseNacional(usuario="123", senha="456")
    xml_destino = isolated_cwd / "xmls"
    pdf_destino = isolated_cwd / "pdfs"
    xml_destino.mkdir()
    pdf_destino.mkdir()

    def fake_enviar_requisicao(metodo, url, **kwargs):
        if kwargs.get("stream"):
            return FakeResponse(chunks=[b"%PDF-1.4", b"-conteudo-pdf"])
        return FakeResponse(text="<root>\n  <item>á</item>\n</root>")

    monkeypatch.setattr(cliente.http, "enviar_requisicao", fake_enviar_requisicao)
    cliente.define_tipo_consulta("emitidas")

    caminho_xml = cliente.baixar_xml("https://exemplo.com/documentos/nota123", str(xml_destino))
    caminho_pdf = cliente.baixar_pdf("https://exemplo.com/documentos/nota123", str(pdf_destino))

    assert Path(caminho_xml).read_text(encoding="utf-8") == "<root><item>á</item></root>"
    assert Path(caminho_pdf).read_bytes() == b"%PDF-1.4-conteudo-pdf"
    assert caminho_xml.endswith("nota123.xml")
    assert caminho_pdf.endswith("nota123.pdf")

