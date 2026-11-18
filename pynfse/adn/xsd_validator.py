"""Validador de Schemas XSD Oficiais v1.01 da NFS-e Nacional via LXML.

Suporta validação de:
- DPS_v1.01.xsd (Declaração de Prestação de Serviços - emissão e substituição)
- pedRegEvento_v1.01.xsd (Pedido de Registro de Evento - cancelamento e101101 e substituição e105102)
- evento_v1.01.xsd (Evento completo assinado)
- NFSe_v1.01.xsd (Nota Fiscal de Serviço Eletrônica completa com IBSCBS)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from lxml import etree

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas_xsd"


class XsdValidator:
    """Validador XSD com cache de schemas compilados em memória."""

    _schemas_cache: Dict[str, etree.XMLSchema] = {}

    @classmethod
    def _get_schema(cls, xsd_filename: str) -> etree.XMLSchema:
        if xsd_filename not in cls._schemas_cache:
            xsd_path = SCHEMAS_DIR / xsd_filename
            if not xsd_path.exists():
                raise FileNotFoundError(f"Schema XSD não encontrado: {xsd_path}")
            parser = etree.XMLParser(load_dtd=False, no_network=True)
            schema_doc = etree.parse(str(xsd_path), parser=parser)
            cls._schemas_cache[xsd_filename] = etree.XMLSchema(schema_doc)
        return cls._schemas_cache[xsd_filename]

    @classmethod
    def _validate(cls, xml_content: str, xsd_filename: str) -> Dict[str, Any]:
        try:
            schema = cls._get_schema(xsd_filename)
            doc = etree.fromstring(xml_content.encode("utf-8"))
            is_valid = schema.validate(doc)
            erros: List[str] = [f"Linha {err.line}: {err.message}" for err in schema.error_log]
            return {"valido": is_valid, "schema": xsd_filename, "erros": erros}
        except Exception as exc:
            return {"valido": False, "schema": xsd_filename, "erros": [f"Erro sintático no XML: {exc}"]}

    @classmethod
    def validar_dps(cls, xml_content: str) -> Dict[str, Any]:
        """Valida o XML contra DPS_v1.01.xsd (compatível com layouts NT 004 v2.0 e NT 009 v1.01)."""
        res = cls._validate(xml_content, "DPS_v1.01.xsd")
        if res["valido"]:
            return res

        # Se o XML estiver no layout da NT 009 v1.01 (<finNFSe> dentro de <infDPS>),
        # normaliza em memória para a estrutura do DPS_v1.01.xsd embutido e valida todos os tipos/campos
        try:
            doc = etree.fromstring(xml_content.encode("utf-8"))
            inf_dps = doc.find("{http://www.sped.fazenda.gov.br/nfse}infDPS")
            if inf_dps is not None and inf_dps.find("{http://www.sped.fazenda.gov.br/nfse}finNFSe") is not None:
                from pynfse.adn.dps_builder import converter_xml_dps_layout_nt

                xml_norm = converter_xml_dps_layout_nt(xml_content, para_nt009=False)
                res_norm = cls._validate(xml_norm, "DPS_v1.01.xsd")
                if res_norm["valido"]:
                    return {"valido": True, "schema": "DPS_v1.01.xsd (NT 009 v1.01)", "erros": []}
        except Exception:
            pass
        return res

    @classmethod
    def validar_evento(cls, xml_content: str) -> Dict[str, Any]:
        """Valida o XML contra pedRegEvento_v1.01.xsd (ou evento_v1.01.xsd se raiz for <evento>)."""
        try:
            doc = etree.fromstring(xml_content.encode("utf-8"))
            local_tag = etree.QName(doc).localname
            if local_tag == "evento":
                return cls._validate(xml_content, "evento_v1.01.xsd")
        except Exception:
            pass
        return cls._validate(xml_content, "pedRegEvento_v1.01.xsd")

    @classmethod
    def validar_nfse(cls, xml_content: str) -> Dict[str, Any]:
        """Valida o XML contra NFSe_v1.01.xsd."""
        return cls._validate(xml_content, "NFSe_v1.01.xsd")
