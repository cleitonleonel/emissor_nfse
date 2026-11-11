from pathlib import Path

import pytest

from pynfse.cliente_nfse import ClienteNfseNacional
from pynfse.danfse_generator import DanfseGenerator
from pynfse.html_to_xml import converter_arquivo_html_para_xml, converter_html_para_xml
from pynfse.xml_parser import extrair_dados_nfse

SAMPLE_HTML = """<!DOCTYPE html>
<html>
<body class="impressao">
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Identificação da NFS-e</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Chave de acesso</span></label><span class="form-control-static texto">32013082253890961000185000000000002126019913119917</span></div>
    <div class="form-group"><label><span>Data de geração</span></label><span class="form-control-static texto">16/01/2026 às 14:24:59-03:00</span></div>
    <div class="form-group"><label><span>Versão</span></label><span class="form-control-static texto">1.01</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Identificação do DPS</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Número</span></label><span class="form-control-static texto">25</span></div>
    <div class="form-group"><label><span>Série</span></label><span class="form-control-static texto">900</span></div>
    <div class="form-group"><label><span>Data de emissão</span></label><span class="form-control-static texto">16/01/2026 às 14:24:59-03:00</span></div>
    <div class="form-group"><label><span>Versão</span></label><span class="form-control-static texto">1.01</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Emitente</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Razão Social</span></label><span class="form-control-static texto">53.890.961 CLEITON LEONEL CRETON</span></div>
    <div class="form-group"><label><span>CNPJ</span></label><span class="form-control-static texto">53.890.961/0001-85</span></div>
    <div class="form-group"><label><span>Inscrição Municipal</span></label><span class="form-control-static texto">-</span></div>
    <div class="form-group"><label><span>Situação Perante o Simples Nacional</span></label><span class="form-control-static texto">Microempreendedor Individual (MEI)</span></div>
    <div class="form-group"><label><span>Regime Especial de Tributação</span></label><span class="form-control-static texto">Nenhum</span></div>
    <div class="form-group"><label><span>Endereço do Estabelecimento/Domicílio</span></label><span class="form-control-static texto">UM AMOR , 114 , Bairro CAMPINA GRANDE , CEP 29144274 , Cariacica/ES</span></div>
    <div class="form-group"><label><span>Telefone</span></label><span class="form-control-static texto">(27)99577-2291</span></div>
    <div class="form-group"><label><span>Email</span></label><span class="form-control-static texto">cleiton.leonel@gmail.com</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Tributação Municipal</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Tributação do ISSQN</span></label><span class="form-control-static texto">1 - Operação Tributável</span></div>
    <div class="form-group"><label><span>Município de Incidência</span></label><span class="form-control-static texto">Cariacica/ES</span></div>
    <div class="form-group"><label><span>Valor do Serviço</span></label><span class="form-control-static texto numero">3.150,00</span></div>
    <div class="form-group"><label><span>Desconto incondicionado</span></label><span class="form-control-static texto numero">0,00</span></div>
    <div class="form-group"><label><span>Base de Cálculo</span></label><span class="form-control-static texto numero">0,00</span></div>
    <div class="form-group"><label><span>Alíquota</span></label><span class="form-control-static texto numero">0,00</span></div>
    <div class="form-group"><label><span>Valor do ISSQN</span></label><span class="form-control-static texto numero">0,00</span></div>
    <div class="form-group"><label><span>Retenção</span></label><span class="form-control-static texto">1 - Não Retido</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Outras Informações</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Versão da Aplicação</span></label><span class="form-control-static texto">EmissorWeb_1.5.0.0</span></div>
    <div class="form-group"><label><span>Ambiente Gerador</span></label><span class="form-control-static texto">2 - Sefin Nacional NFS-e</span></div>
    <div class="form-group"><label><span>Situação da NFS-e</span></label><span class="form-control-static texto">107 - NFS-e do MEI Gerada</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Tomador</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>CNPJ</span></label><span class="form-control-static texto">19.495.981/0001-13</span></div>
    <div class="form-group"><label><span>Inscrição Municipal</span></label><span class="form-control-static texto">-</span></div>
    <div class="form-group"><label><span>Nome/Razão Social</span></label><span class="form-control-static texto">OTMA SOLUCOES LTDA</span></div>
    <div class="form-group"><label><span>Endereço do Estabelecimento/Domicílio</span></label><span class="form-control-static texto">DEMOSTHENES NUNES VIEIRA , 60 /SALA 2 , Bairro ALTO LAJE , CEP 29151260 , Cariacica/ES</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Serviço Prestado</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>País</span></label><span class="form-control-static texto">Brasil</span></div>
    <div class="form-group"><label><span>Município</span></label><span class="form-control-static texto">Cariacica/ES</span></div>
    <div class="form-group"><label><span>Código de Tributação Nacional</span></label><span class="form-control-static texto">010701 - Suporte técnico em informática.</span></div>
    <div class="form-group"><label><span>Item da NBS correspondente ao serviço prestado</span></label><span class="form-control-static texto">115013000 - Serviços de suporte em TI</span></div>
    <div class="form-group"><label><span>Descrição do serviço</span></label><span class="form-control-static texto">Suporte técnico em informática.</span></div>
  </div>
</div>
<div class="panel panel-default panelExterno">
  <h3 class="panel-title">Total dos tributos</h3>
  <div class="panel-body">
    <div class="form-group"><label><span>Opção</span></label><span class="form-control-static texto">Não informar nenhum valor estimado para os Tributos (Decreto 8.264/2014)</span></div>
  </div>
</div>
</body>
</html>
"""


def test_converter_html_para_xml_e_gerar_danfse(tmp_path):
    html_path = tmp_path / "pdfs" / "32013082253890961000185000000000002126019913119917.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(SAMPLE_HTML, encoding="utf-8")

    xml_path = converter_arquivo_html_para_xml(html_path)
    assert Path(xml_path).exists()

    dados = extrair_dados_nfse(xml_path)
    assert dados["numero"] == "21"
    assert dados["chave"] == "32013082253890961000185000000000002126019913119917"
    assert dados["valor"] == 3150.0
    assert dados["cnpj_prestador"] == "53890961000185"
    assert dados["cnpj_tomador"] == "19495981000113"

    pdf_path = tmp_path / "pdfs" / "32013082253890961000185000000000002126019913119917.pdf"
    xml_content = converter_html_para_xml(SAMPLE_HTML)
    gen = DanfseGenerator(xml_content, status="NORMAL")
    gen.gerar_pdf(str(pdf_path))
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_converter_html_erros_validacao():
    with pytest.raises(ValueError, match="vazio"):
        converter_html_para_xml("   ")

    with pytest.raises(ValueError, match="nenhum painel"):
        converter_html_para_xml("<html><body><div>sem paineis</div></body></html>")


def test_cliente_nfse_fallback_html_para_xml_e_pdf(tmp_path, monkeypatch):
    cliente = ClienteNfseNacional(
        usuario="53890961000185",
        senha="123",
        save_path=str(tmp_path),
        path_structure="{CLIENTE}/{ANO}/{MES}",
        razao_social="Cleiton MEI",
    )
    cliente.define_tipo_consulta("emitidas")

    class FakeCaptchaResp:
        url = "https://www.nfse.gov.br/EmissorNacional/ModalCaptcha"
        text = "<html>ModalCaptcha</html>"

        def iter_content(self, chunk_size=8192):
            yield b"<html>ModalCaptcha</html>"

    monkeypatch.setattr(
        cliente.http,
        "enviar_requisicao",
        lambda metodo, url, **kwargs: FakeCaptchaResp(),
    )
    monkeypatch.setattr(cliente, "obter_impressao_html", lambda chave: SAMPLE_HTML)

    chave = "32013082253890961000185000000000002126019913119917"
    xml_saved = cliente.baixar_xml(f"https://www.nfse.gov.br/Download/NFSe/{chave}", "gerada", "16/01/2026")
    assert Path(xml_saved).exists()
    assert xml_saved.endswith(".xml")

    pdf_saved = cliente.baixar_pdf(f"https://www.nfse.gov.br/Download/DANFSe/{chave}", "gerada", "16/01/2026")
    assert Path(pdf_saved).exists()
    assert pdf_saved.endswith(".pdf")
    assert Path(pdf_saved).read_bytes().startswith(b"%PDF")
