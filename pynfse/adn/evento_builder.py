"""Construtor de XML de Eventos da NFS-e Nacional (pedRegEvento_v1.01 e evento_v1.01).

Suporta:
- Cancelamento de NFS-e (Evento e101101)
- Cancelamento de NFS-e por Substituição (Evento e105102)
- Solicitação de Análise Fiscal para Cancelamento (Evento e101103)
- Envelopamento em <evento versao="1.01"> para compartilhamento ADN / Sefin Nacional
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from lxml import etree

NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"


def _clean_digits(val: str | int | None) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _sub(parent: etree._Element, tag: str, text: Optional[str] = None) -> etree._Element:
    el = etree.SubElement(parent, f"{{{NS_NFSE}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def build_evento_cancelamento_xml(
    chave_nfse: str,
    documento_autor: str,
    motivo_codigo: int | str = 1,
    motivo_descricao: str = "Cancelamento efetuado devido a erro cadastral na emissão do documento.",
    ambiente: int | str = 2,
    versao_aplicativo: str = "NFSeManager-1.01",
    data_evento: Optional[str] = None,
) -> str:
    """Constrói o XML <pedRegEvento versao="1.01"> para o Evento e101101 (Cancelamento de NFS-e)."""
    chave_limpa = _clean_digits(chave_nfse)
    if len(chave_limpa) != 50:
        raise ValueError(f"Chave da NFS-e inválida ({len(chave_limpa)} dígitos). Esperado: 50 dígitos.")

    doc_limpo = _clean_digits(documento_autor)
    if len(doc_limpo) not in (11, 14):
        raise ValueError("Documento do autor deve conter 11 (CPF) ou 14 dígitos (CNPJ).")

    cod_motivo = str(motivo_codigo).strip()
    if cod_motivo not in ("1", "2", "9"):
        raise ValueError("Código de motivo inválido. Use: 1 (Erro na Emissão), 2 (Serviço não Prestado) ou 9 (Outros).")

    motivo_txt = (motivo_descricao or "").strip()
    if len(motivo_txt) < 15 or len(motivo_txt) > 255:
        raise ValueError(f"xMotivo deve conter entre 15 e 255 caracteres (atual: {len(motivo_txt)}).")

    tp_amb = "1" if str(ambiente).lower() in ("1", "producao", "produção") else "2"
    codigo_evento = "101101"
    # TSIdPedRegEvt: "PRE" + 56 dígitos (50 da chave + 6 do tipo de evento)
    id_inf_ped_reg = f"PRE{chave_limpa}{codigo_evento}"
    dh_evento = data_evento or datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")

    root = etree.Element(f"{{{NS_NFSE}}}pedRegEvento", nsmap={None: NS_NFSE})
    root.set("versao", "1.01")

    inf_ped = _sub(root, "infPedReg")
    inf_ped.set("Id", id_inf_ped_reg)
    _sub(inf_ped, "tpAmb", tp_amb)
    _sub(inf_ped, "verAplic", versao_aplicativo[:20])
    _sub(inf_ped, "dhEvento", dh_evento)
    if len(doc_limpo) == 14:
        _sub(inf_ped, "CNPJAutor", doc_limpo)
    else:
        _sub(inf_ped, "CPFAutor", doc_limpo)
    _sub(inf_ped, "chNFSe", chave_limpa)

    e101101 = _sub(inf_ped, "e101101")
    _sub(e101101, "xDesc", "Cancelamento de NFS-e")
    _sub(e101101, "cMotivo", cod_motivo)
    _sub(e101101, "xMotivo", motivo_txt)

    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True).decode("utf-8").strip()


def build_evento_substituicao_xml(
    chave_nfse_substituida: str,
    chave_nfse_substituta: str,
    documento_autor: str,
    motivo_codigo: str = "99",
    motivo_descricao: str = "Substituição de NFS-e para retificação de dados operacionais.",
    ambiente: int | str = 2,
    versao_aplicativo: str = "NFSeManager-1.01",
    data_evento: Optional[str] = None,
) -> str:
    """Constrói o XML <pedRegEvento versao="1.01"> para o Evento e105102 (Cancelamento de NFS-e por Substituição)."""
    chave_orig = _clean_digits(chave_nfse_substituida)
    if len(chave_orig) != 50:
        raise ValueError(f"Chave da NFS-e substituída inválida ({len(chave_orig)} dígitos). Esperado: 50 dígitos.")

    chave_sub = _clean_digits(chave_nfse_substituta)
    if len(chave_sub) != 50:
        raise ValueError(f"Chave da NFS-e substituta inválida ({len(chave_sub)} dígitos). Esperado: 50 dígitos.")

    doc_limpo = _clean_digits(documento_autor)
    if len(doc_limpo) not in (11, 14):
        raise ValueError("Documento do autor deve conter 11 (CPF) ou 14 dígitos (CNPJ).")

    cod_motivo = str(motivo_codigo).strip().zfill(2)
    if cod_motivo not in ("01", "02", "03", "04", "05", "99"):
        raise ValueError("Código de motivo de substituição inválido. Use: 01, 02, 03, 04, 05 ou 99.")

    motivo_txt = (motivo_descricao or "").strip()
    if (cod_motivo == "99" or motivo_txt) and (len(motivo_txt) < 15 or len(motivo_txt) > 255):
        raise ValueError(f"xMotivo deve conter entre 15 e 255 caracteres (atual: {len(motivo_txt)}).")

    tp_amb = "1" if str(ambiente).lower() in ("1", "producao", "produção") else "2"
    codigo_evento = "105102"
    id_inf_ped_reg = f"PRE{chave_orig}{codigo_evento}"
    dh_evento = data_evento or datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")

    root = etree.Element(f"{{{NS_NFSE}}}pedRegEvento", nsmap={None: NS_NFSE})
    root.set("versao", "1.01")

    inf_ped = _sub(root, "infPedReg")
    inf_ped.set("Id", id_inf_ped_reg)
    _sub(inf_ped, "tpAmb", tp_amb)
    _sub(inf_ped, "verAplic", versao_aplicativo[:20])
    _sub(inf_ped, "dhEvento", dh_evento)
    if len(doc_limpo) == 14:
        _sub(inf_ped, "CNPJAutor", doc_limpo)
    else:
        _sub(inf_ped, "CPFAutor", doc_limpo)
    _sub(inf_ped, "chNFSe", chave_orig)

    e105102 = _sub(inf_ped, "e105102")
    _sub(e105102, "xDesc", "Cancelamento de NFS-e por Substituição")
    _sub(e105102, "cMotivo", cod_motivo)
    if motivo_txt:
        _sub(e105102, "xMotivo", motivo_txt)
    _sub(e105102, "chSubstituta", chave_sub)

    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True).decode("utf-8").strip()
