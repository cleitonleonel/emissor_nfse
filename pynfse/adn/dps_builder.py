"""Construtor do XML da DPS (Declaração de Prestação de Serviços) v1.01 - Padrão ADN / Sefin Nacional.

Opera diretamente sobre os schemas Pydantic v2 (`DPS`, `Prestador`, `Tomador`, `Endereco`,
`Servico`, `Intermediario`, `Substituicao`), sem necessidade de conversão intermediária para `dict`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from lxml import etree

from pynfse.adn.schemas import (
    DPS,
    Intermediario,
    Prestador,
    Servico,
    Substituicao,
    Tomador,
)

NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"


def clean_digits(val: Any) -> str:
    """Retorna apenas os dígitos numéricos de uma string."""
    return re.sub(r"\D", "", str(val or ""))


def _sub(parent: etree._Element, tag: str, text: Optional[Any] = None) -> etree._Element:
    """Adiciona um subelemento XML ao nó pai e define seu texto se informado."""
    el = etree.SubElement(parent, f"{{{NS_NFSE}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def formatar_id_dps(
    cod_municipio: str,
    documento_emitente: str,
    serie_dps: str,
    numero_dps: int | str,
) -> str:
    """Formata o identificador de 45 caracteres da DPS (TSIdDPS: DPS + 42 dígitos).

    Regra oficial:
    "DPS" + Cód.Mun(7) + Tipo Inscrição Federal(1: 1=CPF, 2=CNPJ) +
    Inscrição Federal(14 - CPF completado com 000 à esquerda) + Série DPS(5) + Núm. DPS(15)
    """
    c_mun = clean_digits(cod_municipio or "3201308").zfill(7)[:7]
    doc = clean_digits(documento_emitente)
    tp_insc = "1" if len(doc) == 11 else "2"
    insc_fed = doc.zfill(14)[:14]
    serie_num = clean_digits(serie_dps or "900").zfill(5)[:5]
    n_dps = clean_digits(numero_dps or 1).zfill(15)[:15]
    return f"DPS{c_mun}{tp_insc}{insc_fed}{serie_num}{n_dps}"


def build_dps_xml_from_schema(dps: DPS) -> str:
    """Constrói o XML `<DPS versao="1.01">` consumindo diretamente os atributos do schema Pydantic `DPS`."""
    prestador = dps.prestador
    tomador = dps.tomador
    servico = dps.servico
    intermediario = dps.intermediario
    subst_data = dps.substituicao or servico.substituicao
    tributacao = dps.obter_tributacao()

    dh_emi = dps.data_emissao_formatada
    d_compet = dps.competencia_formatada

    amb_str = (dps.ambiente or prestador.ambiente or "homologacao").lower()
    tp_amb = "1" if amb_str in ("1", "producao", "produção") else "2"

    c_mun_emi = prestador.codigo_municipio
    doc_prest = prestador.documento_limpo
    if not doc_prest:
        raise ValueError("Documento (CNPJ/CPF) do prestador é obrigatório para gerar a DPS.")

    serie_limpa = clean_digits(dps.serie or "900") or "900"
    num_int = int(clean_digits(dps.numero or 1) or "1")
    id_dps = formatar_id_dps(c_mun_emi, doc_prest, serie_limpa, num_int)

    nsmap = {None: NS_NFSE}
    root = etree.Element(f"{{{NS_NFSE}}}DPS", nsmap=nsmap)
    root.set("versao", "1.01")

    inf_dps = _sub(root, "infDPS")
    inf_dps.set("Id", id_dps)

    _sub(inf_dps, "tpAmb", tp_amb)
    _sub(inf_dps, "dhEmi", dh_emi)
    _sub(inf_dps, "verAplic", dps.versao_aplicativo[:20])
    _sub(inf_dps, "serie", serie_limpa[:5])
    _sub(inf_dps, "nDPS", str(num_int))
    _sub(inf_dps, "dCompet", d_compet)

    tp_emit = str(prestador.tp_emit or "1")
    _sub(inf_dps, "tpEmit", tp_emit)
    if tp_emit in ("2", "3") and prestador.c_motivo_emis_ti:
        _sub(inf_dps, "cMotivoEmisTI", str(prestador.c_motivo_emis_ti))
        if str(prestador.c_motivo_emis_ti) == "4" and prestador.ch_nfse_rej:
            _sub(inf_dps, "chNFSeRej", clean_digits(prestador.ch_nfse_rej))

    _sub(inf_dps, "cLocEmi", c_mun_emi)

    # Bloco opcional <subst> (Substituição de NFS-e via DPS v1.01)
    if subst_data is not None:
        subst_el = _sub(inf_dps, "subst")
        _sub(subst_el, "chSubstda", subst_data.chSubstda)
        _sub(subst_el, "cMotivo", subst_data.cMotivo)
        if subst_data.xMotivo:
            _sub(subst_el, "xMotivo", subst_data.xMotivo[:255])

    # Bloco <prest>
    prest_el = _sub(inf_dps, "prest")
    if len(doc_prest) == 11:
        _sub(prest_el, "CPF", doc_prest)
    else:
        _sub(prest_el, "CNPJ", doc_prest.zfill(14)[:14])

    if prestador.inscricao_municipal:
        _sub(prest_el, "IM", clean_digits(prestador.inscricao_municipal)[:15])
    if prestador.razao_social and (tp_emit != "1" or prestador.incluir_xnome_dps):
        _sub(prest_el, "xNome", str(prestador.razao_social)[:150])

    if prestador.fone:
        fone_p = clean_digits(prestador.fone)
        if 6 <= len(fone_p) <= 20:
            _sub(prest_el, "fone", fone_p)
    if prestador.email:
        _sub(prest_el, "email", str(prestador.email).strip()[:80])

    op_sn = prestador.op_simp_nac
    reg_trib_el = _sub(prest_el, "regTrib")
    _sub(reg_trib_el, "opSimpNac", op_sn)
    if op_sn == "3":
        _sub(reg_trib_el, "regApTribSN", str(prestador.reg_ap_trib_sn or "1"))
    _sub(reg_trib_el, "regEspTrib", str(prestador.reg_esp_trib or "0"))

    # Bloco <toma>
    if tomador is not None:
        doc_toma = tomador.documento_limpo
        if doc_toma or tomador.nif or tomador.c_nao_nif is not None:
            toma_el = _sub(inf_dps, "toma")
            if len(doc_toma) == 14:
                _sub(toma_el, "CNPJ", doc_toma)
            elif len(doc_toma) == 11:
                _sub(toma_el, "CPF", doc_toma)
            elif tomador.nif:
                _sub(toma_el, "NIF", str(tomador.nif)[:40])
            else:
                _sub(toma_el, "cNaoNIF", str(tomador.c_nao_nif or "0"))

            if tomador.inscricao_municipal:
                _sub(toma_el, "IM", clean_digits(tomador.inscricao_municipal)[:15])

            _sub(toma_el, "xNome", str(tomador.razao_social or "Consumidor")[:150])

            end_toma = tomador.endereco
            if end_toma and (end_toma.logradouro or end_toma.cep or end_toma.codigo_municipio):
                end_el = _sub(toma_el, "end")
                end_nac_el = _sub(end_el, "endNac")
                c_mun_toma = end_toma.codigo_municipio or c_mun_emi
                cep_toma = end_toma.cep or "29140000"
                _sub(end_nac_el, "cMun", c_mun_toma)
                _sub(end_nac_el, "CEP", cep_toma)
                _sub(end_el, "xLgr", str(end_toma.logradouro or "Rua Principal")[:255])
                _sub(end_el, "nro", str(end_toma.numero or "S/N")[:60])
                if end_toma.complemento:
                    _sub(end_el, "xCpl", str(end_toma.complemento)[:156])
                _sub(end_el, "xBairro", str(end_toma.bairro or "Centro")[:60])

            if tomador.fone:
                fone_t = clean_digits(tomador.fone)
                if 6 <= len(fone_t) <= 20:
                    _sub(toma_el, "fone", fone_t)
            if tomador.email:
                _sub(toma_el, "email", str(tomador.email).strip()[:80])

    # Bloco opcional <interm>
    if intermediario is not None and intermediario.documento_limpo:
        doc_interm = intermediario.documento_limpo
        interm_el = _sub(inf_dps, "interm")
        if len(doc_interm) == 14:
            _sub(interm_el, "CNPJ", doc_interm)
        else:
            _sub(interm_el, "CPF", doc_interm.zfill(11)[:11])
        _sub(interm_el, "xNome", str(intermediario.razao_social or "Intermediário")[:150])

    # Bloco <serv>
    serv_el = _sub(inf_dps, "serv")
    loc_prest_el = _sub(serv_el, "locPrest")
    c_loc_prest = servico.codigo_municipio_prestacao or c_mun_emi
    if servico.pais_prestacao:
        _sub(loc_prest_el, "cPaisPrestacao", str(servico.pais_prestacao)[:2].upper())
    else:
        _sub(loc_prest_el, "cLocPrestacao", c_loc_prest)

    c_serv_el = _sub(serv_el, "cServ")
    _sub(c_serv_el, "cTribNac", servico.cTribNac)
    if servico.cTribMun:
        _sub(c_serv_el, "cTribMun", clean_digits(servico.cTribMun).zfill(3)[:3])

    _sub(c_serv_el, "xDescServ", servico.descricao.strip()[:2000])

    c_nbs = clean_digits(servico.cNBS or "")
    if c_nbs:
        _sub(c_serv_el, "cNBS", c_nbs.zfill(9)[:9])
    if servico.cIntContrib:
        _sub(c_serv_el, "cIntContrib", str(servico.cIntContrib)[:20])

    if servico.idDocTec or servico.docRef or servico.xInfComp:
        info_compl_el = _sub(serv_el, "infoCompl")
        if servico.idDocTec:
            _sub(info_compl_el, "idDocTec", str(servico.idDocTec)[:40])
        if servico.docRef:
            _sub(info_compl_el, "docRef", str(servico.docRef)[:255])
        if servico.xInfComp:
            _sub(info_compl_el, "xInfComp", str(servico.xInfComp)[:2000])

    # Bloco <valores>
    valores_el = _sub(inf_dps, "valores")
    v_serv_prest_el = _sub(valores_el, "vServPrest")
    v_serv_val = float(servico.valor or tributacao.get("valor_servicos") or 0.0)
    if servico.valor_recebido is not None:
        _sub(v_serv_prest_el, "vReceb", f"{float(servico.valor_recebido):.2f}")
    _sub(v_serv_prest_el, "vServ", f"{v_serv_val:.2f}")

    v_desc_incond = float(servico.desconto_incondicionado or tributacao.get("desconto_incondicionado") or 0.0)
    v_desc_cond = float(servico.desconto_condicionado or tributacao.get("desconto_condicionado") or 0.0)
    if v_desc_incond > 0 or v_desc_cond > 0:
        v_desc_el = _sub(valores_el, "vDescCondIncond")
        if v_desc_incond > 0:
            _sub(v_desc_el, "vDescIncond", f"{v_desc_incond:.2f}")
        if v_desc_cond > 0:
            _sub(v_desc_el, "vDescCond", f"{v_desc_cond:.2f}")

    # Sub-bloco <trib>
    trib_el = _sub(valores_el, "trib")
    iss_data = tributacao.get("iss") or {}
    trib_mun_el = _sub(trib_el, "tribMun")
    trib_issqn = str(iss_data.get("trib_issqn") or "1")
    _sub(trib_mun_el, "tribISSQN", trib_issqn)
    tp_ret_issqn = str(iss_data.get("tp_ret_issqn") or (2 if iss_data.get("retido") else 1))
    _sub(trib_mun_el, "tpRetISSQN", tp_ret_issqn)
    p_aliq_iss = iss_data.get("aliquota")
    if p_aliq_iss is not None and float(p_aliq_iss) > 0 and op_sn != "2":
        _sub(trib_mun_el, "pAliq", f"{float(p_aliq_iss):.2f}")

    # Tributos Federais (<tribFed>)
    ret_fed = tributacao.get("retencoes_federais") or {}
    v_pis = float(ret_fed.get("pis") or 0.0)
    v_cofins = float(ret_fed.get("cofins") or 0.0)
    v_irrf = float(ret_fed.get("irrf") or 0.0)
    v_csll = float(ret_fed.get("csll") or 0.0)
    v_inss = float(ret_fed.get("inss") or 0.0)

    if any(v > 0 for v in (v_pis, v_cofins, v_irrf, v_csll, v_inss)):
        trib_fed_el = _sub(trib_el, "tribFed")
        if v_pis > 0 or v_cofins > 0:
            pc_el = _sub(trib_fed_el, "piscofins")
            _sub(pc_el, "CST", str(ret_fed.get("cst_pis_cofins") or "01").zfill(2))
            v_bc_pc = float(ret_fed.get("base_calculo_pis_cofins") or v_serv_val)
            _sub(pc_el, "vBCPisCofins", f"{v_bc_pc:.2f}")
            _sub(pc_el, "pAliqPis", f"{float(ret_fed.get('aliquota_pis') or 0.65):.2f}")
            _sub(pc_el, "pAliqCofins", f"{float(ret_fed.get('aliquota_cofins') or 3.00):.2f}")
            _sub(pc_el, "vPis", f"{v_pis:.2f}")
            _sub(pc_el, "vCofins", f"{v_cofins:.2f}")
            _sub(pc_el, "tpRetPisCofins", str(ret_fed.get("tp_ret_pis_cofins") or "1"))
        if v_inss > 0:
            _sub(trib_fed_el, "vRetCP", f"{v_inss:.2f}")
        if v_irrf > 0:
            _sub(trib_fed_el, "vRetIRRF", f"{v_irrf:.2f}")
        if v_csll > 0:
            _sub(trib_fed_el, "vRetCSLL", f"{v_csll:.2f}")

    # <totTrib> conforme opSimpNac (Regras E0710 / E0712 / E0713)
    tot_trib_el = _sub(trib_el, "totTrib")
    if op_sn == "2":
        _sub(tot_trib_el, "indTotTrib", "0")
    elif op_sn == "3" and tributacao.get("p_tot_trib_sn") is not None:
        _sub(tot_trib_el, "pTotTribSN", f"{float(tributacao['p_tot_trib_sn']):.2f}")
    elif tributacao.get("v_tot_trib"):
        vt = tributacao["v_tot_trib"]
        v_tot_el = _sub(tot_trib_el, "vTotTrib")
        _sub(v_tot_el, "vTotTribFed", f"{float(vt.get('fed', 0.0)):.2f}")
        _sub(v_tot_el, "vTotTribEst", f"{float(vt.get('est', 0.0)):.2f}")
        _sub(v_tot_el, "vTotTribMun", f"{float(vt.get('mun', 0.0)):.2f}")
    else:
        _sub(tot_trib_el, "indTotTrib", "0")

    # Bloco <IBSCBS> (Reforma Tributária v1.01)
    if dps.incluir_ibscbs:
        reforma = tributacao.get("reforma_tributaria") or {}
        c_ind_op = clean_digits(servico.indop or reforma.get("cIndOp") or "100301").zfill(6)[:6]
        c_class_trib = clean_digits(servico.cClassTrib or reforma.get("cClassTrib") or "000001").zfill(6)[:6]
        cst_ibscbs = clean_digits(servico.cst or reforma.get("cst") or c_class_trib[:3]).zfill(3)[:3]

        ibscbs_el = _sub(inf_dps, "IBSCBS")
        _sub(ibscbs_el, "finNFSe", str(servico.finNFSe or "0"))
        if servico.indFinal is not None:
            _sub(ibscbs_el, "indFinal", str(servico.indFinal))
        _sub(ibscbs_el, "cIndOp", c_ind_op)

        if servico.tpOper is not None:
            _sub(ibscbs_el, "tpOper", str(servico.tpOper))
        if servico.refNFSe:
            g_ref_el = _sub(ibscbs_el, "gRefNFSe")
            refs = servico.refNFSe if isinstance(servico.refNFSe, list) else [servico.refNFSe]
            for ref_key in refs:
                _sub(g_ref_el, "refNFSe", clean_digits(ref_key))

        if (
            servico.tpEnteGov is not None
            or (reforma.get("compras_governamentais") or {}).get("tpEnteGov") is not None
        ):
            tp_gov = (
                servico.tpEnteGov
                if servico.tpEnteGov is not None
                else reforma["compras_governamentais"]["tpEnteGov"]
            )
            _sub(ibscbs_el, "tpEnteGov", str(tp_gov))

        ind_dest = str(servico.indDest if servico.indDest is not None else "0")
        _sub(ibscbs_el, "indDest", ind_dest)

        # Valores e Tributação IBSCBS
        val_ibscbs_el = _sub(ibscbs_el, "valores")
        trib_ibscbs_el = _sub(val_ibscbs_el, "trib")
        g_ibscbs_el = _sub(trib_ibscbs_el, "gIBSCBS")
        _sub(g_ibscbs_el, "CST", cst_ibscbs)
        _sub(g_ibscbs_el, "cClassTrib", c_class_trib)

        cred_pres = reforma.get("credito_presumido") or servico.cCredPres
        if cred_pres:
            c_cp = cred_pres.get("cCredPres") if isinstance(cred_pres, dict) else str(cred_pres)
            if c_cp:
                _sub(g_ibscbs_el, "cCredPres", clean_digits(c_cp).zfill(2)[:2])

        trib_reg = reforma.get("tributacao_regular") or servico.tributacao_regular
        if trib_reg and trib_reg.get("cClassTribReg"):
            g_reg_el = _sub(g_ibscbs_el, "gTribRegular")
            cod_reg = clean_digits(trib_reg["cClassTribReg"]).zfill(6)[:6]
            cst_reg = clean_digits(trib_reg.get("CSTReg") or cod_reg[:3]).zfill(3)[:3]
            _sub(g_reg_el, "CSTReg", cst_reg)
            _sub(g_reg_el, "cClassTribReg", cod_reg)

        ibs_uf_info = reforma.get("ibs_uf") or {}
        ibs_mun_info = reforma.get("ibs_mun") or {}
        cbs_info = reforma.get("cbs") or {}
        p_dif_uf = float(ibs_uf_info.get("pDifUF") or 0.0)
        p_dif_mun = float(ibs_mun_info.get("pDifMun") or 0.0)
        p_dif_cbs = float(cbs_info.get("pDifCBS") or 0.0)
        if any(p > 0 for p in (p_dif_uf, p_dif_mun, p_dif_cbs)):
            g_dif_el = _sub(g_ibscbs_el, "gDif")
            _sub(g_dif_el, "pDifUF", f"{p_dif_uf:.2f}")
            _sub(g_dif_el, "pDifMun", f"{p_dif_mun:.2f}")
            _sub(g_dif_el, "pDifCBS", f"{p_dif_cbs:.2f}")

    xml_bytes = etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    return xml_bytes.decode("utf-8").strip()


def build_dps_xml(
    prestador: DPS | Prestador | Dict[str, Any],
    tomador: Optional[Tomador | Dict[str, Any]] = None,
    servico: Optional[Servico | Dict[str, Any]] = None,
    tributacao: Optional[Dict[str, Any]] = None,
    serie_dps: str = "900",
    numero_dps: int | str = 1,
    data_competencia: Optional[str] = None,
    data_emissao: Optional[str] = None,
    ambiente: Optional[str] = None,
    substituicao: Optional[Substituicao | Dict[str, Any]] = None,
    intermediario: Optional[Intermediario | Dict[str, Any]] = None,
    incluir_ibscbs: bool = True,
    versao_aplicativo: str = "NFSeManager-1.01",
) -> str:
    """Gera o XML da DPS v1.01 validando os parâmetros via schema Pydantic `DPS`."""
    if isinstance(prestador, DPS):
        return build_dps_xml_from_schema(prestador)

    if servico is None:
        raise ValueError("O parâmetro `servico` é obrigatório quando `prestador` não é uma instância de `DPS`.")

    dps_schema = DPS(
        prestador=prestador if isinstance(prestador, Prestador) else Prestador.model_validate(prestador),
        tomador=(
            tomador
            if isinstance(tomador, Tomador) or tomador is None
            else Tomador.model_validate(tomador)
        ),
        servico=servico if isinstance(servico, Servico) else Servico.model_validate(servico),
        intermediario=(
            intermediario
            if isinstance(intermediario, Intermediario) or intermediario is None
            else Intermediario.model_validate(intermediario)
        ),
        substituicao=(
            substituicao
            if isinstance(substituicao, Substituicao) or substituicao is None
            else Substituicao.model_validate(substituicao)
        ),
        tributacao=tributacao,
        serie=serie_dps,
        numero=numero_dps,
        competencia=data_competencia,
        data_emissao=data_emissao,
        ambiente=ambiente or (prestador.ambiente if isinstance(prestador, Prestador) else prestador.get("ambiente")) or "homologacao",
        incluir_ibscbs=incluir_ibscbs,
        versao_aplicativo=versao_aplicativo,
    )
    return build_dps_xml_from_schema(dps_schema)
