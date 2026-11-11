"""
Módulo para extração de dados de XMLs da NFS-e Nacional (padrão SPED).
Utiliza apenas a stdlib (xml.etree.ElementTree) — sem dependências extras.

Namespace oficial: http://www.sped.fazenda.gov.br/nfse
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, cast

from pynfse.constants import NS
from pynfse.utils import find_xml_text, parse_datetime

logger = logging.getLogger(__name__)


def _find_text(root: Optional[ET.Element], xpath: str) -> Optional[str]:
    """Busca um elemento pelo XPath com namespace e retorna seu texto, ou None."""
    return find_xml_text(root, xpath)


def _parse_float(value: Optional[str]) -> float:
    """Converte string monetária para float com segurança."""
    if not value:
        return 0.0
    try:
        return float(value.replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Converte string ISO 8601 (com ou sem offset) para datetime."""
    return parse_datetime(value)


def extrair_dados_nfse(xml_path: str) -> dict:
    """
    Lê um arquivo XML da NFS-e Nacional e extrai os campos relevantes.

    Args:
        xml_path: Caminho absoluto ou relativo do arquivo XML.

    Returns:
        dict com as chaves:
            - numero (str | None): número da NFS-e (<nNFSe>)
            - chave (str | None): ID da nota (<infNFSe Id=...>)
            - valor (float): valor líquido da nota (<vLiq>)
            - valor_servico (float): valor bruto do serviço (<vServ>)
            - data_emissao (datetime | None): data de processamento (<dhProc>)
            - cnpj_prestador (str | None): CNPJ do emitente (<emit><CNPJ>)
            - cnpj_tomador (str | None): CNPJ do tomador (<toma><CNPJ>)
            - cpf_tomador (str | None): CPF do tomador (<toma><CPF>)
            - nome_tomador (str | None): nome do tomador (<toma><xNome>)
            - descricao_servico (str | None): descrição (<xDescServ>)
            - status_code (str | None): código de status (<cStat>)
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Erro ao parsear XML {xml_path}: {e}")
        return {}
    except FileNotFoundError:
        logger.error(f"Arquivo XML não encontrado: {xml_path}")
        return {}

    # Navega até o nó raiz infNFSe (pode ser diretamente ou dentro de NFSe)
    inf_el = root.find("pynfse:infNFSe", NS)
    inf = cast(ET.Element, inf_el if inf_el is not None else root)

    # Extrai o atributo Id da chave da nota
    chave = inf.get("Id", "").replace("NFS", "") if inf is not None else None

    # Número da nota
    numero = _find_text(inf, "pynfse:nNFSe")

    # Data de processamento — mais precisa que a data de emissão da DPS
    data_str = _find_text(inf, "pynfse:dhProc")
    data_emissao = _parse_datetime(data_str)

    # Se não achar dhProc, busca dhEmi dentro da DPS
    if data_emissao is None:
        dps = inf.find("pynfse:DPS/pynfse:infDPS", NS)
        if dps is not None:
            data_emissao = _parse_datetime(_find_text(dps, "pynfse:dhEmi"))

    # Valor líquido da NFS-e (campo principal)
    valor_liq = _parse_float(_find_text(inf, "pynfse:valores/pynfse:vLiq"))

    # Valor bruto do serviço (dentro da DPS)
    dps_node = inf.find("pynfse:DPS/pynfse:infDPS", NS)
    valor_serv = 0.0
    cnpj_tomador = None
    cpf_tomador = None
    nome_tomador = None
    descricao = None

    if dps_node is not None:
        valor_serv = _parse_float(_find_text(dps_node, "pynfse:valores/pynfse:vServPrest/pynfse:vServ"))
        # Tomador
        toma = dps_node.find("pynfse:toma", NS)
        if toma is not None:
            cnpj_tomador = _find_text(toma, "pynfse:CNPJ")
            cpf_tomador = _find_text(toma, "pynfse:CPF")
            nome_tomador = _find_text(toma, "pynfse:xNome")

        # Descrição do serviço
        descricao = _find_text(dps_node, "pynfse:serv/pynfse:cServ/pynfse:xDescServ")

    # Prestador
    emit = inf.find("pynfse:emit", NS)
    cnpj_prestador = _find_text(emit, "pynfse:CNPJ") if emit is not None else None

    # Status
    status_code = _find_text(inf, "pynfse:cStat")

    return {
        "numero": numero,
        "chave": chave or None,
        "valor": valor_liq if valor_liq > 0 else valor_serv,
        "valor_servico": valor_serv,
        "data_emissao": data_emissao,
        "cnpj_prestador": cnpj_prestador,
        "cnpj_tomador": cnpj_tomador,
        "cpf_tomador": cpf_tomador,
        "nome_tomador": nome_tomador,
        "descricao_servico": descricao,
        "status_code": status_code,
    }
