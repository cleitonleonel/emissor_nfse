"""Módulo de utilitários e funções auxiliares do pynfse."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pynfse.constants import NS, NS_NFSE


def clean_digits(val: Any) -> str:
    """Retorna apenas os dígitos numéricos de uma string ou número."""
    if val is None:
        return ""
    return re.sub(r"\D", "", str(val))


def parse_datetime(val: Any) -> Optional[datetime]:
    """Converte valores variados (datetime, ISO 8601, pt-BR) em objeto datetime.

    Formatos suportados:
      - Objeto datetime existente
      - '2026-07-20T15:00:00-03:00' ou '2026-07-20T15:00:00Z'
      - '2026-07-20T15:00:00'
      - '2026-07-20'
      - '20/07/2026 às 15:00:00-03:00' ou '20/07/2026 15:00:00'
      - '20/07/2026'
      - '2026-07-20 15:00:00'
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val

    cleaned = str(val).strip()
    if not cleaned or cleaned == "-":
        return None

    # Formato pt-BR com 'às' ou espaço: 20/07/2026 às 15:00:00
    m_br = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*(?:às\s*)?(\d{2}:\d{2}:\d{2})?",
        cleaned,
    )
    if m_br and "/" in cleaned:
        date_str, time_str = m_br.groups()
        fmt = "%d/%m/%Y %H:%M:%S" if time_str else "%d/%m/%Y"
        target = f"{date_str} {time_str}" if time_str else date_str
        try:
            return datetime.strptime(target, fmt)
        except ValueError:
            pass

    # Formato ISO ou SQL: 2026-07-20T15:00:00 ou 2026-07-20 15:00:00
    try:
        if "T" in cleaned:
            # Remove o offset de timezone para normalizar como naive datetime
            return datetime.strptime(cleaned[:19], "%Y-%m-%dT%H:%M:%S")
        elif " " in cleaned:
            return datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S")
        else:
            return datetime.strptime(cleaned[:10], "%Y-%m-%d")
    except Exception:
        return None


def format_date(val: Any, include_time: bool = False) -> str:
    """Formata datetime ou string para o padrão brasileiro 'DD/MM/AAAA' (ou 'DD/MM/AAAA HH:MM:SS')."""
    if not val or val == "-":
        return "-"
    dt = parse_datetime(val)
    if not dt:
        return str(val)
    if include_time or (isinstance(val, str) and ("T" in val or " " in val)):
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    return dt.strftime("%d/%m/%Y")


def parse_currency(val: Optional[str], default: float = 0.0) -> float:
    """Converte valor monetário formatado (ex: '1.668,00', 'R$ 1.668,00') para float."""
    if not val:
        return default
    cleaned = str(val).replace("R$", "").replace("%", "").strip()
    if not cleaned or cleaned == "-":
        return default
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return default


def format_currency(val: float | int | Decimal | str) -> str:
    """Formata valor numérico para o padrão de moeda pt-BR ('R$ 1.500,00')."""
    try:
        num = float(val)
    except (ValueError, TypeError):
        return "R$ 0,00"
    return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percent(val: float | int | Decimal | str) -> str:
    """Formata valor numérico para percentual ('5,00%')."""
    try:
        num = float(val)
    except (ValueError, TypeError):
        return "0,00%"
    return f"{num:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def format_cnpj_cpf(val: str) -> str:
    """Formata string numérica como CNPJ (14 dígitos) ou CPF (11 dígitos)."""
    digits = clean_digits(val)
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return val


def format_cep(val: str) -> str:
    """Formata string numérica como CEP (XXXXX-XXX)."""
    digits = clean_digits(val)
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return val


def format_phone(val: str) -> str:
    """Formata telefone brasileiro com DDD."""
    if not val or val == "-":
        return "-"
    digits = clean_digits(val)
    if not digits:
        return "-"
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    elif len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    elif len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return val


def extrair_codigo_inicial(val: Optional[str], default: str = "") -> str:
    """Extrai os dígitos iniciais de uma descrição com código (ex: '1 - Operação Tributável' -> '1')."""
    if not val:
        return default
    m = re.match(r"^(\d+)", str(val).strip())
    return m.group(1) if m else default


def find_xml_text(root: Optional[ET.Element], xpath: str, default: Optional[str] = None) -> Optional[str]:
    """Busca elemento XML via XPath com o namespace padrão da NFS-e e retorna o texto limpo."""
    if root is None:
        return default
    el = root.find(xpath, NS)
    if el is not None and el.text:
        return el.text.strip()
    return default


def find_xml_float(root: Optional[ET.Element], xpath: str, default: float = 0.0) -> float:
    """Busca elemento XML via XPath com o namespace padrão e converte o valor para float."""
    txt = find_xml_text(root, xpath)
    if not txt or txt == "-":
        return default
    try:
        return float(txt)
    except ValueError:
        return default


def append_documento_xml(parent: Any, documento: str, subelement_fn: Any = None) -> None:
    """Adiciona a tag `<CNPJ>` ou `<CPF>` ao elemento pai conforme a quantidade de dígitos."""
    limpo = clean_digits(documento)
    if not limpo:
        return
    if subelement_fn is None:
        if type(parent).__module__.startswith("lxml"):
            from lxml import etree

            def _fn(p, tag, txt):
                el = etree.SubElement(p, f"{{{NS_NFSE}}}{tag}")
                el.text = str(txt)
                return el

            subelement_fn = _fn
        else:

            def _fn(p, tag, txt):
                el = ET.SubElement(p, tag)
                el.text = str(txt)
                return el

            subelement_fn = _fn

    if len(limpo) == 14:
        subelement_fn(parent, "CNPJ", limpo)
    elif len(limpo) == 11:
        subelement_fn(parent, "CPF", limpo)
