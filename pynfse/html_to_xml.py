"""
Conversor de HTML de impressão da NFS-e Nacional (Visualizar/Impressao) para XML padrão SPED.

Quando o download oficial de XML/PDF no portal Emissor Nacional é bloqueado por Captcha,
o portal permite obter o HTML da visualização de impressão (renderizado via XSLT a partir do XML).
Este módulo reconstrói o XML padrão SPED (`http://www.sped.fazenda.gov.br/nfse`) a partir desse HTML,
permitindo o parse via `extrair_dados_nfse` e a geração de DANFSe em PDF via `DanfseGenerator`.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

from bs4 import BeautifulSoup

from pynfse.constants import MUNICIPIOS_NOME_PARA_IBGE, NS_NFSE
from pynfse.utils import clean_digits, extrair_codigo_inicial, parse_currency

logger = logging.getLogger(__name__)


def _clean_text(val: Optional[str]) -> str:
    """Normaliza espaços internos e remove quebras de linha."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val).strip()


def _only_digits(val: Optional[str]) -> str:
    """Retorna apenas os dígitos numéricos de uma string."""
    return clean_digits(val)


def _parse_decimal_str(val: Optional[str], default: str = "0.00") -> str:
    """Converte valor monetário pt-BR (ex: '1.668,00') para string decimal ('1668.00')."""
    if not val or _clean_text(val) == "-":
        return default
    return f"{parse_currency(val):.2f}"


def _parse_datetime_iso(val: Optional[str]) -> str:
    """
    Converte data do HTML (ex: '31/01/2026 às 00:00:00-03:00' ou '31/01/2026')
    para ISO 8601 ('2026-01-31T00:00:00-03:00').
    """
    if not val:
        return ""
    cleaned = _clean_text(val)
    match = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*(?:às\s*)?(\d{2}:\d{2}:\d{2})?([+-]\d{2}:\d{2}|Z)?",
        cleaned,
    )
    if match:
        date_part, time_part, tz_part = match.groups()
        dt = datetime.strptime(date_part, "%d/%m/%Y")
        time_str = time_part or "00:00:00"
        tz_str = tz_part or "-03:00"
        return f"{dt.strftime('%Y-%m-%d')}T{time_str}{tz_str}"
    return cleaned


def _parse_endereco_html(raw_endereco: str, default_cmun: str = "3201308") -> Dict[str, str]:
    """
    Extrai componentes de endereço do formato XSLT do Emissor Nacional:
    Ex:
      '29151-260 - RUA DEMÓSTHENES NUNES VIEIRA, 60 , 0 , Bairro ALTO LAJE , CEP 29151260 , Cariacica/ES'
      'VITORIA GABURRO BAPTISTA , 66 /QUADRA7A LOTE 9 , Bairro SANTA BARBARA , CEP 29145019 , Cariacica/ES'
    """
    result = {
        "xLgr": "",
        "nro": "S/N",
        "xCpl": "",
        "xBairro": "",
        "CEP": "",
        "xMun": "",
        "UF": "",
        "cMun": default_cmun,
    }
    if not raw_endereco or _clean_text(raw_endereco) == "-":
        return result

    text = _clean_text(raw_endereco)

    # Divide pelo marcador ', Bairro '
    if ", Bairro " in text:
        before_bairro, after_bairro = text.split(", Bairro ", 1)
    elif "Bairro " in text:
        before_bairro, after_bairro = text.split("Bairro ", 1)
    else:
        before_bairro, after_bairro = text, ""

    # Logradouro, número e complemento ficam em before_bairro
    # No XSLT, o número é separado do logradouro pela última vírgula
    if "," in before_bairro:
        lgr_part, nro_part = before_bairro.rsplit(",", 1)
        result["xLgr"] = lgr_part.strip()
        nro_part = nro_part.strip()
        if "/" in nro_part:
            nro_val, cpl_val = nro_part.split("/", 1)
            result["nro"] = nro_val.strip() or "0"
            result["xCpl"] = cpl_val.strip()
        else:
            result["nro"] = nro_part or "0"
    else:
        result["xLgr"] = before_bairro.strip()

    # Bairro, CEP e Município/UF ficam em after_bairro
    if after_bairro:
        if ", CEP " in after_bairro:
            bairro_part, after_cep = after_bairro.split(", CEP ", 1)
            result["xBairro"] = bairro_part.strip()
        elif "CEP " in after_bairro:
            bairro_part, after_cep = after_bairro.split("CEP ", 1)
            result["xBairro"] = bairro_part.strip().rstrip(",")
        else:
            result["xBairro"] = after_bairro.strip()
            after_cep = ""

        if after_cep:
            parts = [p.strip() for p in after_cep.split(",") if p.strip()]
            if parts:
                result["CEP"] = _only_digits(parts[0])
            if len(parts) > 1 and "/" in parts[-1]:
                mun_str, uf_str = parts[-1].rsplit("/", 1)
                result["xMun"] = mun_str.strip()
                result["UF"] = uf_str.strip().upper()
                ibge = MUNICIPIOS_NOME_PARA_IBGE.get((result["xMun"].upper(), result["UF"]))
                if ibge:
                    result["cMun"] = ibge

    return result


def _extract_panels(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    """Extrai um dicionário {titulo_painel: {label: valor}} do HTML de impressão."""
    panels: Dict[str, Dict[str, str]] = {}
    for panel in soup.find_all("div", class_="panel"):
        title_el = panel.find(["h3", "h4"], class_="panel-title")
        if not title_el:
            continue
        title = _clean_text(title_el.get_text())
        fields: Dict[str, str] = panels.setdefault(title, {})
        for fg in panel.find_all("div", class_="form-group"):
            label_el = fg.find("label")
            val_el = fg.find("span", class_="form-control-static")
            if label_el and val_el:
                label = _clean_text(label_el.get_text())
                val = _clean_text(val_el.get_text())
                fields[label] = val
    return panels


def _sub(parent: ET.Element, tag: str, text: Optional[str] = None, **attrib: str) -> ET.Element:
    """Cria um subelemento XML e define seu texto se fornecido."""
    el = ET.SubElement(parent, tag, attrib)
    if text is not None:
        el.text = str(text)
    return el


def converter_html_para_xml(html_content: str) -> str:
    """
    Converte o conteúdo HTML da página de impressão do Emissor Nacional
    em uma string XML padrão SPED (`<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">`).
    """
    if not html_content or not html_content.strip():
        raise ValueError("Conteúdo HTML vazio para conversão em XML.")

    # Se já for um XML válido de NFSe, retorna o próprio conteúdo normalizado
    stripped = html_content.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<NFSe") or stripped.startswith("<CompNfse"):
        return stripped

    soup = BeautifulSoup(html_content, "html.parser")
    panels = _extract_panels(soup)

    if not panels:
        raise ValueError("Estrutura HTML inválida: nenhum painel da NFS-e foi encontrado.")

    p_nfse = panels.get("Identificação da NFS-e", {})
    p_dps = panels.get("Identificação do DPS", {})
    p_emit = panels.get("Emitente", {})
    p_trib_mun = panels.get("Tributação Municipal", {})
    p_outras = panels.get("Outras Informações", {})
    p_toma = panels.get("Tomador", {})
    p_interm = panels.get("Intermediário", {})
    p_serv = panels.get("Serviço Prestado", {})
    p_compl = panels.get("Informações Complementares", {})
    p_trib_fed = panels.get("Tributação Federal", {})
    p_tot_trib = panels.get("Total dos tributos", {})

    chave = _only_digits(p_nfse.get("Chave de acesso", ""))
    if not chave:
        raise ValueError("Chave de acesso não encontrada no HTML da NFS-e.")

    versao_nfse = p_nfse.get("Versão") or p_dps.get("Versão") or "1.00"
    versao_dps = p_dps.get("Versão") or versao_nfse

    # Decomposição da chave de 50 dígitos da NFS-e Nacional:
    # cLocEmi(7) + ambGer(1) + tpInsc(1) + CNPJ/CPF(14) + nNFSe(13) + AAMM(4) + tpEmis(1) + nDFSe(8) + cDV(1)
    c_loc_key = chave[0:7] if len(chave) >= 7 and chave[0:7].isdigit() else "3201308"
    amb_ger_key = chave[7:8] if len(chave) >= 8 and chave[7:8].isdigit() else "2"
    tp_insc_key = chave[8:9] if len(chave) >= 9 and chave[8:9].isdigit() else "2"
    doc_emit_key = chave[9:23] if len(chave) >= 23 and chave[9:23].isdigit() else ""
    n_nfse_key = str(int(chave[23:36])) if len(chave) >= 36 and chave[23:36].isdigit() else ""
    aamm_key = chave[36:40] if len(chave) >= 40 and chave[36:40].isdigit() else ""
    n_dfse_key = str(int(chave[41:49])) if len(chave) >= 49 and chave[41:49].isdigit() else ""

    n_dps = _only_digits(p_dps.get("Número", "")) or n_nfse_key or "1"
    n_nfse = n_nfse_key or n_dps
    serie_dps = _only_digits(p_dps.get("Série", "")) or "900"

    dh_proc = _parse_datetime_iso(p_nfse.get("Data de geração", ""))
    dh_emi = _parse_datetime_iso(p_dps.get("Data de emissão", "")) or dh_proc
    if not dh_proc:
        dh_proc = dh_emi

    # Competência (YYYY-MM-01)
    if dh_emi and len(dh_emi) >= 10:
        d_compet = f"{dh_emi[:8]}01"
    elif len(aamm_key) == 4:
        d_compet = f"20{aamm_key[:2]}-{aamm_key[2:4]}-01"
    else:
        d_compet = datetime.now().strftime("%Y-%m-01")

    # Endereço do emitente
    end_emit = _parse_endereco_html(
        p_emit.get("Endereço do Estabelecimento/Domicílio", ""),
        default_cmun=c_loc_key,
    )
    c_loc_emi = end_emit["cMun"] or c_loc_key
    x_loc_emi = (end_emit["xMun"] or "CARIACICA").upper()

    # Local de prestação e incidência
    mun_serv_raw = p_serv.get("Município", "")
    x_loc_prest = mun_serv_raw.split("/")[0].strip() if "/" in mun_serv_raw else (end_emit["xMun"] or "Cariacica")
    uf_prest = mun_serv_raw.split("/")[1].strip().upper() if "/" in mun_serv_raw else (end_emit["UF"] or "ES")
    c_loc_prest = MUNICIPIOS_NOME_PARA_IBGE.get((x_loc_prest.upper(), uf_prest), c_loc_emi)

    mun_incid_raw = p_trib_mun.get("Município de Incidência", "")
    x_loc_incid = mun_incid_raw.split("/")[0].strip() if "/" in mun_incid_raw else x_loc_prest
    uf_incid = mun_incid_raw.split("/")[1].strip().upper() if "/" in mun_incid_raw else uf_prest
    c_loc_incid = MUNICIPIOS_NOME_PARA_IBGE.get((x_loc_incid.upper(), uf_incid), c_loc_prest)

    # Tributação Nacional e NBS
    trib_nac_raw = p_serv.get("Código de Tributação Nacional", "")
    if " - " in trib_nac_raw:
        c_trib_part, x_trib_part = trib_nac_raw.split(" - ", 1)
        c_trib_nac = _only_digits(c_trib_part) or "010701"
        x_trib_nac = x_trib_part.strip()
    else:
        c_trib_nac = _only_digits(trib_nac_raw) or "010701"
        x_trib_nac = trib_nac_raw.strip() or p_serv.get("Descrição do serviço", "Serviço prestado")

    nbs_raw = p_serv.get("Item da NBS correspondente ao serviço prestado", "")
    c_nbs = _only_digits(nbs_raw.split(" - ")[0] if " - " in nbs_raw else nbs_raw)

    x_desc_serv = p_serv.get("Descrição do serviço", "") or x_trib_nac

    # Outras informações
    ver_aplic = p_outras.get("Versão da Aplicação", "EmissorWeb_1.0")
    amb_ger = extrair_codigo_inicial(p_outras.get("Ambiente Gerador", ""), default=amb_ger_key)
    tp_emis = "2" if amb_ger == "1" else "1"

    c_stat = extrair_codigo_inicial(p_outras.get("Situação da NFS-e", "100"), default="100")

    # Dados do Emitente
    emit_doc = _only_digits(p_emit.get("CNPJ") or p_emit.get("CPF") or doc_emit_key)
    emit_im = p_emit.get("Inscrição Municipal", "")
    emit_im = "" if emit_im == "-" else _only_digits(emit_im) or emit_im
    emit_nome = p_emit.get("Razão Social") or p_emit.get("Nome/Razão Social") or ""
    emit_fone = _only_digits(p_emit.get("Telefone", ""))
    emit_email = p_emit.get("Email") or p_emit.get("E-mail") or ""
    if emit_email == "-":
        emit_email = ""

    # Simples Nacional
    simp_raw = p_emit.get("Situação Perante o Simples Nacional", "").lower()
    if "mei" in simp_raw or "microempreendedor" in simp_raw:
        op_simp_nac = "2"
        reg_ap_sn = ""
    elif "microempresa" in simp_raw or "pequeno porte" in simp_raw or "me/epp" in simp_raw:
        op_simp_nac = "3"
        reg_ap_sn = "1"
    else:
        op_simp_nac = "1"
        reg_ap_sn = ""

    reg_esp_trib = extrair_codigo_inicial(p_emit.get("Regime Especial de Tributação", ""), default="0")

    # Valores Municipais e Federais
    v_serv = _parse_decimal_str(p_trib_mun.get("Valor do Serviço"))
    v_desc_incond = _parse_decimal_str(p_trib_mun.get("Desconto incondicionado"))
    v_bc = _parse_decimal_str(p_trib_mun.get("Base de Cálculo"))
    p_aliq = _parse_decimal_str(p_trib_mun.get("Alíquota"))
    v_issqn = _parse_decimal_str(p_trib_mun.get("Valor do ISSQN"))

    trib_issqn = extrair_codigo_inicial(p_trib_mun.get("Tributação do ISSQN", "1"), default="1")
    tp_ret_issqn = extrair_codigo_inicial(p_trib_mun.get("Retenção", "1"), default="1")

    v_irrf = _parse_decimal_str(p_trib_fed.get("IRRF"))
    v_csll = _parse_decimal_str(p_trib_fed.get("Contribuições Sociais - Retidas"))
    v_cp = _parse_decimal_str(p_trib_fed.get("Contribuição Previdenciária - Retida"))
    v_pis = _parse_decimal_str(p_trib_fed.get("PIS - Débito Apuração Própria"))
    v_cofins = _parse_decimal_str(p_trib_fed.get("COFINS - Débito Apuração Própria"))

    # Cálculo do valor líquido (vLiq)
    v_serv_f = float(v_serv)
    v_desc_f = float(v_desc_incond)
    v_ret_iss_f = float(v_issqn) if tp_ret_issqn in ("2", "3") else 0.0
    v_ret_fed_f = float(v_irrf) + float(v_csll) + float(v_cp)
    v_liq_f = max(0.0, v_serv_f - v_desc_f - v_ret_iss_f - v_ret_fed_f)
    v_liq = f"{v_liq_f:.2f}"

    # Construção da árvore XML
    ET.register_namespace("", NS_NFSE)
    root = ET.Element("NFSe", {"xmlns": NS_NFSE, "versao": versao_nfse})
    inf_nfse = _sub(root, "infNFSe", Id=f"NFS{chave}")

    _sub(inf_nfse, "xLocEmi", x_loc_emi)
    _sub(inf_nfse, "xLocPrestacao", x_loc_prest)
    _sub(inf_nfse, "nNFSe", n_nfse)
    _sub(inf_nfse, "cLocIncid", c_loc_incid)
    _sub(inf_nfse, "xLocIncid", x_loc_incid)
    _sub(inf_nfse, "xTribNac", x_trib_nac)
    _sub(inf_nfse, "verAplic", ver_aplic)
    _sub(inf_nfse, "ambGer", amb_ger)
    _sub(inf_nfse, "tpEmis", tp_emis)
    _sub(inf_nfse, "cStat", c_stat)
    _sub(inf_nfse, "dhProc", dh_proc)
    if n_dfse_key:
        _sub(inf_nfse, "nDFSe", n_dfse_key)

    # <emit>
    emit_el = _sub(inf_nfse, "emit")
    if len(emit_doc) == 11:
        _sub(emit_el, "CPF", emit_doc)
    else:
        _sub(emit_el, "CNPJ", emit_doc.zfill(14) if emit_doc else "00000000000000")
    if emit_im:
        _sub(emit_el, "IM", emit_im)
    _sub(emit_el, "xNome", emit_nome)

    ender_nac = _sub(emit_el, "enderNac")
    _sub(ender_nac, "xLgr", end_emit["xLgr"])
    _sub(ender_nac, "nro", end_emit["nro"])
    if end_emit["xCpl"]:
        _sub(ender_nac, "xCpl", end_emit["xCpl"])
    _sub(ender_nac, "xBairro", end_emit["xBairro"])
    _sub(ender_nac, "cMun", c_loc_emi)
    _sub(ender_nac, "UF", end_emit["UF"] or "ES")
    _sub(ender_nac, "CEP", end_emit["CEP"])

    if emit_fone:
        _sub(emit_el, "fone", emit_fone)
    if emit_email:
        _sub(emit_el, "email", emit_email)

    # <valores> de infNFSe
    val_nfse = _sub(inf_nfse, "valores")
    _sub(val_nfse, "vBC", v_bc)
    _sub(val_nfse, "pAliqAplic", p_aliq)
    _sub(val_nfse, "vISSQN", v_issqn)
    _sub(val_nfse, "vLiq", v_liq)

    # <DPS>
    dps_el = _sub(inf_nfse, "DPS", versao=versao_dps)
    tp_insc_dps = "1" if len(emit_doc) == 11 else tp_insc_key
    dps_id = f"DPS{c_loc_emi}{tp_insc_dps}{emit_doc.zfill(14)}{serie_dps.zfill(5)}{n_dps.zfill(15)}"
    inf_dps = _sub(dps_el, "infDPS", Id=dps_id)

    _sub(inf_dps, "tpAmb", "1")
    _sub(inf_dps, "dhEmi", dh_emi)
    _sub(inf_dps, "verAplic", ver_aplic)
    _sub(inf_dps, "serie", serie_dps)
    _sub(inf_dps, "nDPS", n_dps)
    _sub(inf_dps, "dCompet", d_compet)
    _sub(inf_dps, "tpEmit", "1")
    _sub(inf_dps, "cLocEmi", c_loc_emi)

    # <prest>
    prest_el = _sub(inf_dps, "prest")
    if len(emit_doc) == 11:
        _sub(prest_el, "CPF", emit_doc)
    else:
        _sub(prest_el, "CNPJ", emit_doc.zfill(14) if emit_doc else "00000000000000")
    if emit_im:
        _sub(prest_el, "IM", emit_im)
    if emit_fone:
        _sub(prest_el, "fone", emit_fone)
    if emit_email:
        _sub(prest_el, "email", emit_email)
    reg_trib = _sub(prest_el, "regTrib")
    _sub(reg_trib, "opSimpNac", op_simp_nac)
    if reg_ap_sn:
        _sub(reg_trib, "regApTribSN", reg_ap_sn)
    _sub(reg_trib, "regEspTrib", reg_esp_trib)

    # <toma>
    toma_doc = _only_digits(p_toma.get("CNPJ") or p_toma.get("CPF") or "")
    toma_nome = p_toma.get("Nome/Razão Social") or p_toma.get("Razão Social") or ""
    if toma_doc or (toma_nome and toma_nome != "-"):
        toma_el = _sub(inf_dps, "toma")
        if len(toma_doc) == 11:
            _sub(toma_el, "CPF", toma_doc)
        elif toma_doc:
            _sub(toma_el, "CNPJ", toma_doc.zfill(14))
        toma_im = p_toma.get("Inscrição Municipal", "")
        if toma_im and toma_im != "-":
            _sub(toma_el, "IM", toma_im)
        if toma_nome and toma_nome != "-":
            _sub(toma_el, "xNome", toma_nome)

        end_toma = _parse_endereco_html(
            p_toma.get("Endereço do Estabelecimento/Domicílio", ""),
            default_cmun=c_loc_prest,
        )
        if end_toma["xLgr"]:
            end_toma_el = _sub(toma_el, "end")
            end_nac_toma = _sub(end_toma_el, "endNac")
            _sub(end_nac_toma, "cMun", end_toma["cMun"])
            if end_toma["UF"]:
                _sub(end_nac_toma, "UF", end_toma["UF"])
            _sub(end_nac_toma, "CEP", end_toma["CEP"])
            _sub(end_toma_el, "xLgr", end_toma["xLgr"])
            _sub(end_toma_el, "nro", end_toma["nro"])
            if end_toma["xCpl"]:
                _sub(end_toma_el, "xCpl", end_toma["xCpl"])
            _sub(end_toma_el, "xBairro", end_toma["xBairro"])

        toma_fone = _only_digits(p_toma.get("Telefone", ""))
        if toma_fone:
            _sub(toma_el, "fone", toma_fone)
        toma_email = p_toma.get("Email") or p_toma.get("E-mail") or ""
        if toma_email and toma_email != "-":
            _sub(toma_el, "email", toma_email)

    # <interm> (se presente)
    interm_doc = _only_digits(p_interm.get("CNPJ") or p_interm.get("CPF") or "")
    if interm_doc:
        interm_el = _sub(inf_dps, "interm")
        if len(interm_doc) == 11:
            _sub(interm_el, "CPF", interm_doc)
        else:
            _sub(interm_el, "CNPJ", interm_doc.zfill(14))
        interm_nome = p_interm.get("Nome/Razão Social") or p_interm.get("Razão Social") or ""
        if interm_nome and interm_nome != "-":
            _sub(interm_el, "xNome", interm_nome)

    # <serv>
    serv_el = _sub(inf_dps, "serv")
    loc_prest_el = _sub(serv_el, "locPrest")
    _sub(loc_prest_el, "cLocPrestacao", c_loc_prest)
    c_serv_el = _sub(serv_el, "cServ")
    _sub(c_serv_el, "cTribNac", c_trib_nac)
    _sub(c_serv_el, "xDescServ", x_desc_serv)
    if c_nbs:
        _sub(c_serv_el, "cNBS", c_nbs)

    inf_compl_txt = p_compl.get("Informações complementares", "")
    if inf_compl_txt and inf_compl_txt != "-":
        _sub(serv_el, "infoCompl", inf_compl_txt)

    # <valores> de infDPS
    val_dps = _sub(inf_dps, "valores")
    v_serv_prest = _sub(val_dps, "vServPrest")
    _sub(v_serv_prest, "vServ", v_serv)
    if float(v_desc_incond) > 0:
        v_desc_el = _sub(val_dps, "vDescCondIncond")
        _sub(v_desc_el, "vDescIncond", v_desc_incond)

    trib_el = _sub(val_dps, "trib")
    trib_mun_el = _sub(trib_el, "tribMun")
    _sub(trib_mun_el, "tribISSQN", trib_issqn)
    _sub(trib_mun_el, "tpRetISSQN", tp_ret_issqn)

    trib_fed_el = _sub(trib_el, "tribFed")
    if float(v_pis) > 0 or float(v_cofins) > 0:
        piscofins_el = _sub(trib_fed_el, "piscofins")
        _sub(piscofins_el, "vPis", v_pis)
        _sub(piscofins_el, "vCofins", v_cofins)
    if float(v_irrf) > 0:
        _sub(trib_fed_el, "vRetIRRF", v_irrf)
    if float(v_cp) > 0:
        _sub(trib_fed_el, "vRetCP", v_cp)
    if float(v_csll) > 0:
        _sub(trib_fed_el, "vRetCSLL", v_csll)

    tot_trib_el = _sub(trib_el, "totTrib")
    if "Federal" in p_tot_trib or "Municipal" in p_tot_trib or "Estadual" in p_tot_trib:
        v_tot_trib_el = _sub(tot_trib_el, "vTotTrib")
        _sub(v_tot_trib_el, "vTotTribFed", _parse_decimal_str(p_tot_trib.get("Federal")))
        _sub(v_tot_trib_el, "vTotTribEst", _parse_decimal_str(p_tot_trib.get("Estadual")))
        _sub(v_tot_trib_el, "vTotTribMun", _parse_decimal_str(p_tot_trib.get("Municipal")))
    else:
        _sub(tot_trib_el, "indTotTrib", "0")

    xml_body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>{xml_body}'


def converter_arquivo_html_para_xml(
    html_path: Union[str, Path],
    xml_output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Lê um arquivo `.html` de impressão da NFS-e, converte para XML padrão SPED
    e salva no disco (por padrão trocando `/pdfs/` por `/xmls/` e `.html` por `.xml`).

    Returns:
        str: Caminho do arquivo `.xml` salvo.
    """
    src = Path(html_path)
    if not src.exists():
        raise FileNotFoundError(f"Arquivo HTML não encontrado: {src}")

    html_content = src.read_text(encoding="utf-8", errors="replace")
    xml_content = converter_html_para_xml(html_content)

    if xml_output_path:
        dst = Path(xml_output_path)
    else:
        dst_str = str(src.with_suffix(".xml")).replace("/pdfs/", "/xmls/").replace("\\pdfs\\", "\\xmls\\")
        dst = Path(dst_str)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(xml_content, encoding="utf-8")
    logger.info(f"HTML convertido para XML com sucesso em: {dst}")
    return str(dst)
