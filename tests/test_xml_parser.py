from datetime import datetime
from pathlib import Path

import core.xml_parser as xml_parser

NS = "http://www.sped.fazenda.gov.br/nfse"


def _write_xml(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_helpers_e_parsing_basico():
    assert xml_parser._find_text(None, "nfse:algo") is None
    assert xml_parser._parse_float(None) == 0.0
    assert xml_parser._parse_float("1,23") == 1.23
    assert xml_parser._parse_float("abc") == 0.0
    assert xml_parser._parse_float(123) == 0.0
    assert xml_parser._parse_datetime(None) is None
    assert xml_parser._parse_datetime("2025-09-01T16:24:00-03:00") == datetime(
        2025, 9, 1, 16, 24, 0
    )
    assert xml_parser._parse_datetime("2025-09-01") == datetime(2025, 9, 1)
    assert xml_parser._parse_datetime("invalido") is None


def test_extrair_dados_nfse_xml_completo(tmp_path):
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<CompNfse xmlns="{NS}">
  <infNFSe Id="NFS123">
    <nNFSe>987</nNFSe>
    <dhProc>2025-09-01T16:24:00-03:00</dhProc>
    <valores>
      <vLiq>100,50</vLiq>
    </valores>
    <DPS>
      <infDPS>
        <dhEmi>2025-08-31T11:22:33</dhEmi>
        <valores>
          <vServPrest>
            <vServ>99,10</vServ>
          </vServPrest>
        </valores>
        <toma>
          <CNPJ>12345678000123</CNPJ>
          <CPF>12345678901</CPF>
          <xNome>Tomador Teste</xNome>
        </toma>
        <serv>
          <cServ>
            <xDescServ>Descricao do servico</xDescServ>
          </cServ>
        </serv>
      </infDPS>
    </DPS>
    <emit><CNPJ>99999999000199</CNPJ></emit>
    <cStat>100</cStat>
  </infNFSe>
</CompNfse>
"""
    xml_path = _write_xml(tmp_path, "nfse.xml", xml)

    dados = xml_parser.extrair_dados_nfse(str(xml_path))

    assert dados == {
        "numero": "987",
        "chave": "123",
        "valor": 100.5,
        "valor_servico": 99.1,
        "data_emissao": datetime(2025, 9, 1, 16, 24, 0),
        "cnpj_prestador": "99999999000199",
        "cnpj_tomador": "12345678000123",
        "cpf_tomador": "12345678901",
        "nome_tomador": "Tomador Teste",
        "descricao_servico": "Descricao do servico",
        "status_code": "100",
    }


def test_extrair_dados_nfse_fallback_para_dh_emi_e_valor_servico(tmp_path):
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<infNFSe xmlns="{NS}" Id="NFS456">
  <nNFSe>654</nNFSe>
  <DPS>
    <infDPS>
      <dhEmi>2025-09-02T01:02:03</dhEmi>
      <valores>
        <vServPrest>
          <vServ>12,34</vServ>
        </vServPrest>
      </valores>
      <toma>
        <CPF>98765432100</CPF>
        <xNome>Tomador Sem CNPJ</xNome>
      </toma>
    </infDPS>
  </DPS>
</infNFSe>
"""
    xml_path = _write_xml(tmp_path, "nfse_sem_dhproc.xml", xml)

    dados = xml_parser.extrair_dados_nfse(str(xml_path))

    assert dados["chave"] == "456"
    assert dados["numero"] == "654"
    assert dados["valor"] == 12.34
    assert dados["valor_servico"] == 12.34
    assert dados["data_emissao"] == datetime(2025, 9, 2, 1, 2, 3)
    assert dados["cnpj_prestador"] is None
    assert dados["cnpj_tomador"] is None
    assert dados["cpf_tomador"] == "98765432100"
    assert dados["nome_tomador"] == "Tomador Sem CNPJ"
    assert dados["descricao_servico"] is None
    assert dados["status_code"] is None


def test_extrair_dados_nfse_retorna_vazio_em_erros(tmp_path):
    xml_invalido = _write_xml(tmp_path, "invalido.xml", "<xml><quebrado>")

    assert xml_parser.extrair_dados_nfse(str(xml_invalido)) == {}
    assert xml_parser.extrair_dados_nfse(str(tmp_path / "nao_existe.xml")) == {}

