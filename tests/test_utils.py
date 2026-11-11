import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

from pynfse.utils import (
    append_documento_xml,
    clean_digits,
    extrair_codigo_inicial,
    find_xml_float,
    find_xml_text,
    format_cep,
    format_cnpj_cpf,
    format_currency,
    format_date,
    format_percent,
    format_phone,
    parse_currency,
    parse_datetime,
)


def test_clean_digits():
    assert clean_digits(None) == ""
    assert clean_digits("123.456.789-00") == "12345678900"
    assert clean_digits(12345) == "12345"
    assert clean_digits("abc-12-def") == "12"


def test_parse_datetime_and_format_date():
    assert parse_datetime(None) is None
    assert parse_datetime("-") is None
    dt = datetime(2026, 7, 20, 15, 0, 0)
    assert parse_datetime(dt) == dt
    assert parse_datetime("2026-07-20T15:00:00-03:00") == dt
    assert parse_datetime("2026-07-20 15:00:00") == dt
    assert parse_datetime("2026-07-20") == datetime(2026, 7, 20)
    assert parse_datetime("20/07/2026 às 15:00:00-03:00") == dt
    assert parse_datetime("20/07/2026") == datetime(2026, 7, 20)
    assert parse_datetime("invalid-date") is None

    assert format_date(None) == "-"
    assert format_date("-") == "-"
    assert format_date("2026-07-20") == "20/07/2026"
    assert format_date("2026-07-20T15:00:00-03:00", include_time=True) == "20/07/2026 15:00:00"


def test_currency_and_percent():
    assert parse_currency(None) == 0.0
    assert parse_currency("-") == 0.0
    assert parse_currency("1.500,50") == 1500.50
    assert parse_currency("R$ 2.000,00") == 2000.00
    assert parse_currency("invalid") == 0.0

    assert format_currency(1500.5) == "R$ 1.500,50"
    assert format_currency(Decimal("2000.00")) == "R$ 2.000,00"
    assert format_currency("invalid") == "R$ 0,00"

    assert format_percent(5.0) == "5,00%"
    assert format_percent("invalid") == "0,00%"


def test_format_documents_and_contacts():
    assert format_cnpj_cpf("12345678000195") == "12.345.678/0001-95"
    assert format_cnpj_cpf("12345678901") == "123.456.789-01"
    assert format_cnpj_cpf("123") == "123"

    assert format_cep("29140000") == "29140-000"
    assert format_cep("123") == "123"

    assert format_phone(None) == "-"
    assert format_phone("-") == "-"
    assert format_phone("27999998888") == "(27) 99999-8888"
    assert format_phone("2733334444") == "(27) 3333-4444"
    assert format_phone("999998888") == "99999-8888"
    assert format_phone("33334444") == "3333-4444"
    assert format_phone("abc") == "-"


def test_extrair_codigo_inicial():
    assert extrair_codigo_inicial(None) == ""
    assert extrair_codigo_inicial("1 - Operação Tributável") == "1"
    assert extrair_codigo_inicial("107 - NFS-e do MEI Gerada") == "107"
    assert extrair_codigo_inicial("Texto sem codigo", default="0") == "0"


def test_xml_helpers():
    xml = """<root xmlns="http://www.sped.fazenda.gov.br/nfse">
        <valor>123.45</valor>
        <texto>Exemplo</texto>
    </root>"""
    root = ET.fromstring(xml)
    assert find_xml_text(root, "pynfse:texto") == "Exemplo"
    assert find_xml_text(root, "pynfse:inexistente", default="padrao") == "padrao"
    assert find_xml_float(root, "pynfse:valor") == 123.45
    assert find_xml_float(root, "pynfse:inexistente") == 0.0

    # append_documento_xml
    doc_root = ET.Element("toma")
    append_documento_xml(doc_root, "12.345.678/0001-95")
    assert doc_root.find("CNPJ").text == "12345678000195"

    doc_root_cpf = ET.Element("toma")
    append_documento_xml(doc_root_cpf, "123.456.789-01")
    assert doc_root_cpf.find("CPF").text == "12345678901"
