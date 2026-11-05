"""Construtor do XML da DPS (Declaração de Prestação de Serviços) v1.01 - Padrão ADN / Sefin Nacional.

Suporta:
- Emissão normal de NFS-e via DPS v1.01 (<DPS versao="1.01">)
- Substituição de NFS-e via DPS v1.01 (incluindo o grupo <subst><chSubstda>...<cMotivo>...<xMotivo>...)
- Preenchimento completo dos grupos tributários municipais (tribMun), federais (tribFed),
  total de tributos (totTrib conforme regime opSimpNac) e Reforma Tributária (<IBSCBS> v1.01:
  CST, cClassTrib, cIndOp, cCredPres, gTribRegular, gDif, gReeRepRes, imovel, dest, gRefNFSe).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from lxml import etree

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


def build_dps_xml(
    prestador: Dict[str, Any],
    tomador: Optional[Dict[str, Any]],
    servico: Dict[str, Any],
    tributacao: Dict[str, Any],
    serie_dps: str = "900",
    numero_dps: int | str = 1,
    data_competencia: Optional[str] = None,
    data_emissao: Optional[str] = None,
    ambiente: Optional[str] = None,
    substituicao: Optional[Dict[str, Any]] = None,
    intermediario: Optional[Dict[str, Any]] = None,
    incluir_ibscbs: bool = True,
    versao_aplicativo: str = "NFSeManager-1.01",
) -> str:
    """Gera o XML da DPS v1.01 em total conformidade com DPS_v1.01.xsd e RN DPS_NFS-e."""
    agora_dt = datetime.now()
    dh_emi = data_emissao or agora_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    d_compet = data_competencia or dh_emi[:10]

    amb_str = (ambiente or prestador.get("ambiente") or "homologacao").lower()
    tp_amb = "1" if amb_str in ("1", "producao", "produção") else "2"

    c_mun_emi = clean_digits(prestador.get("codigo_municipio") or "3201308").zfill(7)[:7]
    doc_prest = clean_digits(prestador.get("cnpj") or prestador.get("cpf") or prestador.get("documento") or "")
    if not doc_prest:
        raise ValueError("Documento (CNPJ/CPF) do prestador é obrigatório para gerar a DPS.")

    serie_limpa = clean_digits(serie_dps or "900") or "900"
    num_int = int(clean_digits(numero_dps or 1) or "1")
    id_dps = formatar_id_dps(c_mun_emi, doc_prest, serie_limpa, num_int)

    nsmap = {None: NS_NFSE}
    root = etree.Element(f"{{{NS_NFSE}}}DPS", nsmap=nsmap)
    root.set("versao", "1.01")

    inf_dps = _sub(root, "infDPS")
    inf_dps.set("Id", id_dps)

    _sub(inf_dps, "tpAmb", tp_amb)
    _sub(inf_dps, "dhEmi", dh_emi)
    _sub(inf_dps, "verAplic", versao_aplicativo[:20])
    _sub(inf_dps, "serie", serie_limpa[:5])
    _sub(inf_dps, "nDPS", str(num_int))
    _sub(inf_dps, "dCompet", d_compet)

    tp_emit = str(prestador.get("tp_emit") or "1")
    _sub(inf_dps, "tpEmit", tp_emit)
    if tp_emit in ("2", "3") and prestador.get("c_motivo_emis_ti"):
        _sub(inf_dps, "cMotivoEmisTI", str(prestador["c_motivo_emis_ti"]))
        if str(prestador["c_motivo_emis_ti"]) == "4" and prestador.get("ch_nfse_rej"):
            _sub(inf_dps, "chNFSeRej", clean_digits(prestador["ch_nfse_rej"]))

    _sub(inf_dps, "cLocEmi", c_mun_emi)

    # Bloco opcional <subst> (Substituição de NFS-e via DPS v1.01)
    subst_data = substituicao or servico.get("substituicao")
    if subst_data and subst_data.get("chSubstda"):
        ch_substda = clean_digits(subst_data["chSubstda"])
        if len(ch_substda) != 50:
            raise ValueError(
                f"Chave da NFS-e a ser substituída (chSubstda) deve ter 50 dígitos (informado: {len(ch_substda)})."
            )
        c_motivo_sub = str(subst_data.get("cMotivo") or "99").zfill(2)
        if c_motivo_sub not in {"01", "02", "03", "04", "05", "99"}:
            raise ValueError(f"cMotivo de substituição inválido: '{c_motivo_sub}'. Use 01, 02, 03, 04, 05 ou 99.")
        x_motivo_sub = (subst_data.get("xMotivo") or "").strip()
        if c_motivo_sub == "99" and len(x_motivo_sub) < 15:
            raise ValueError(
                "Para substituição com cMotivo='99' (Outros), xMotivo é obrigatório (mínimo 15 caracteres)."
            )

        subst_el = _sub(inf_dps, "subst")
        _sub(subst_el, "chSubstda", ch_substda)
        _sub(subst_el, "cMotivo", c_motivo_sub)
        if x_motivo_sub:
            _sub(subst_el, "xMotivo", x_motivo_sub[:255])

    # Bloco <prest>
    prest_el = _sub(inf_dps, "prest")
    if len(doc_prest) == 11:
        _sub(prest_el, "CPF", doc_prest)
    else:
        _sub(prest_el, "CNPJ", doc_prest.zfill(14)[:14])

    if prestador.get("inscricao_municipal"):
        _sub(prest_el, "IM", clean_digits(prestador["inscricao_municipal"])[:15])
    if prestador.get("razao_social") and tp_emit != "1":
        # Nota: pela RN E0120, xNome do prestador na DPS só é informado quando emitente não é o próprio prestador,
        # mas o XSD permite xNome opcionalmente (minOccurs=0). Se o usuário solicitar explicitamente incluir_nome_prestador, incluímos.
        _sub(prest_el, "xNome", str(prestador["razao_social"])[:150])
    elif prestador.get("incluir_xnome_dps") and prestador.get("razao_social"):
        _sub(prest_el, "xNome", str(prestador["razao_social"])[:150])

    if prestador.get("fone"):
        fone_p = clean_digits(prestador["fone"])
        if 6 <= len(fone_p) <= 20:
            _sub(prest_el, "fone", fone_p)
    if prestador.get("email"):
        _sub(prest_el, "email", str(prestador["email"]).strip()[:80])

    regime_str = str(prestador.get("regime") or prestador.get("regime_tributario") or "normal").lower()
    if regime_str in ("3", "simples", "me_epp"):
        op_sn = "3"
    elif regime_str in ("2", "mei"):
        op_sn = "2"
    else:
        op_sn = "1"

    reg_trib_el = _sub(prest_el, "regTrib")
    _sub(reg_trib_el, "opSimpNac", op_sn)
    if op_sn == "3":
        reg_ap_sn = str(prestador.get("reg_ap_trib_sn") or prestador.get("regime_apuracao_sn") or "1")
        _sub(reg_trib_el, "regApTribSN", reg_ap_sn)
    reg_esp = str(prestador.get("reg_esp_trib") or prestador.get("regime_especial") or "0")
    _sub(reg_trib_el, "regEspTrib", reg_esp)

    # Bloco <toma>
    if tomador:
        doc_toma = clean_digits(tomador.get("documento") or tomador.get("cnpj") or tomador.get("cpf") or "")
        if doc_toma or tomador.get("nif") or tomador.get("c_nao_nif") is not None:
            toma_el = _sub(inf_dps, "toma")
            if len(doc_toma) == 14:
                _sub(toma_el, "CNPJ", doc_toma)
            elif len(doc_toma) == 11:
                _sub(toma_el, "CPF", doc_toma)
            elif tomador.get("nif"):
                _sub(toma_el, "NIF", str(tomador["nif"])[:40])
            else:
                _sub(toma_el, "cNaoNIF", str(tomador.get("c_nao_nif", "0")))

            if tomador.get("inscricao_municipal"):
                _sub(toma_el, "IM", clean_digits(tomador["inscricao_municipal"])[:15])

            _sub(toma_el, "xNome", str(tomador.get("razao_social") or tomador.get("nome") or "Consumidor")[:150])

            if tomador.get("logradouro") or tomador.get("cep") or tomador.get("codigo_municipio"):
                end_el = _sub(toma_el, "end")
                end_nac_el = _sub(end_el, "endNac")
                c_mun_toma = clean_digits(tomador.get("codigo_municipio") or c_mun_emi).zfill(7)[:7]
                cep_toma = clean_digits(tomador.get("cep") or "29140000").zfill(8)[:8]
                _sub(end_nac_el, "cMun", c_mun_toma)
                _sub(end_nac_el, "CEP", cep_toma)
                _sub(end_el, "xLgr", str(tomador.get("logradouro") or "Rua Principal")[:255])
                _sub(end_el, "nro", str(tomador.get("numero") or "S/N")[:60])
                if tomador.get("complemento"):
                    _sub(end_el, "xCpl", str(tomador["complemento"])[:156])
                _sub(end_el, "xBairro", str(tomador.get("bairro") or "Centro")[:60])

            if tomador.get("fone"):
                fone_t = clean_digits(tomador["fone"])
                if 6 <= len(fone_t) <= 20:
                    _sub(toma_el, "fone", fone_t)
            if tomador.get("email"):
                _sub(toma_el, "email", str(tomador["email"]).strip()[:80])

    # Bloco opcional <interm>
    if intermediario and (intermediario.get("documento") or intermediario.get("cnpj") or intermediario.get("cpf")):
        doc_interm = clean_digits(
            intermediario.get("documento") or intermediario.get("cnpj") or intermediario.get("cpf")
        )
        interm_el = _sub(inf_dps, "interm")
        if len(doc_interm) == 14:
            _sub(interm_el, "CNPJ", doc_interm)
        else:
            _sub(interm_el, "CPF", doc_interm.zfill(11)[:11])
        _sub(interm_el, "xNome", str(intermediario.get("razao_social") or "Intermediário")[:150])

    # Bloco <serv>
    serv_el = _sub(inf_dps, "serv")
    loc_prest_el = _sub(serv_el, "locPrest")
    c_loc_prest = clean_digits(servico.get("codigo_municipio_prestacao") or c_mun_emi).zfill(7)[:7]
    if servico.get("pais_prestacao"):
        _sub(loc_prest_el, "cPaisPrestacao", str(servico["pais_prestacao"])[:2].upper())
    else:
        _sub(loc_prest_el, "cLocPrestacao", c_loc_prest)

    c_serv_el = _sub(serv_el, "cServ")
    c_trib_nac = clean_digits(servico.get("cTribNac") or "010101").zfill(6)[:6]
    _sub(c_serv_el, "cTribNac", c_trib_nac)
    if servico.get("cTribMun"):
        _sub(c_serv_el, "cTribMun", clean_digits(servico["cTribMun"]).zfill(3)[:3])

    x_desc_serv = (servico.get("discriminacao") or servico.get("descricao") or "Prestação de serviços").strip()
    _sub(c_serv_el, "xDescServ", x_desc_serv[:2000])

    c_nbs = clean_digits(servico.get("cNBS") or servico.get("nbs") or "")
    if c_nbs:
        _sub(c_serv_el, "cNBS", c_nbs.zfill(9)[:9])
    if servico.get("cIntContrib"):
        _sub(c_serv_el, "cIntContrib", str(servico["cIntContrib"])[:20])

    if servico.get("infoCompl") or servico.get("idDocTec") or servico.get("xInfComp"):
        info_compl_el = _sub(serv_el, "infoCompl")
        if servico.get("idDocTec"):
            _sub(info_compl_el, "idDocTec", str(servico["idDocTec"])[:40])
        if servico.get("docRef"):
            _sub(info_compl_el, "docRef", str(servico["docRef"])[:255])
        if servico.get("xInfComp"):
            _sub(info_compl_el, "xInfComp", str(servico["xInfComp"])[:2000])

    # Bloco <valores>
    valores_el = _sub(inf_dps, "valores")
    v_serv_prest_el = _sub(valores_el, "vServPrest")
    v_serv_val = float(servico.get("valor") or servico.get("valor_servicos") or tributacao.get("valor_servicos") or 0.0)
    if servico.get("valor_recebido") is not None:
        _sub(v_serv_prest_el, "vReceb", f"{float(servico['valor_recebido']):.2f}")
    _sub(v_serv_prest_el, "vServ", f"{v_serv_val:.2f}")

    v_desc_incond = float(servico.get("desconto_incondicionado") or tributacao.get("desconto_incondicionado") or 0.0)
    v_desc_cond = float(servico.get("desconto_condicionado") or tributacao.get("desconto_condicionado") or 0.0)
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
        # MEI: indTotTrib=0
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
    if incluir_ibscbs:
        reforma = tributacao.get("reforma_tributaria") or {}
        c_ind_op = clean_digits(
            servico.get("indop") or servico.get("cIndOp") or reforma.get("cIndOp") or "100301"
        ).zfill(6)[:6]
        c_class_trib = clean_digits(servico.get("cClassTrib") or reforma.get("cClassTrib") or "000001").zfill(6)[:6]
        cst_ibscbs = clean_digits(servico.get("cst") or reforma.get("cst") or c_class_trib[:3]).zfill(3)[:3]

        ibscbs_el = _sub(inf_dps, "IBSCBS")
        _sub(ibscbs_el, "finNFSe", str(servico.get("finNFSe") or "0"))
        if servico.get("indFinal") is not None:
            _sub(ibscbs_el, "indFinal", str(servico["indFinal"]))
        _sub(ibscbs_el, "cIndOp", c_ind_op)

        if servico.get("tpOper") is not None:
            _sub(ibscbs_el, "tpOper", str(servico["tpOper"]))
        if servico.get("refNFSe"):
            g_ref_el = _sub(ibscbs_el, "gRefNFSe")
            refs = servico["refNFSe"] if isinstance(servico["refNFSe"], list) else [servico["refNFSe"]]
            for ref_key in refs:
                _sub(g_ref_el, "refNFSe", clean_digits(ref_key))

        if (
            servico.get("tpEnteGov") is not None
            or (reforma.get("compras_governamentais") or {}).get("tpEnteGov") is not None
        ):
            tp_gov = servico.get("tpEnteGov") or reforma["compras_governamentais"]["tpEnteGov"]
            _sub(ibscbs_el, "tpEnteGov", str(tp_gov))

        ind_dest = str(servico.get("indDest") if servico.get("indDest") is not None else "0")
        _sub(ibscbs_el, "indDest", ind_dest)

        # Valores e Tributação IBSCBS
        val_ibscbs_el = _sub(ibscbs_el, "valores")
        trib_ibscbs_el = _sub(val_ibscbs_el, "trib")
        g_ibscbs_el = _sub(trib_ibscbs_el, "gIBSCBS")
        _sub(g_ibscbs_el, "CST", cst_ibscbs)
        _sub(g_ibscbs_el, "cClassTrib", c_class_trib)

        cred_pres = reforma.get("credito_presumido") or servico.get("cCredPres")
        if cred_pres:
            c_cp = cred_pres.get("cCredPres") if isinstance(cred_pres, dict) else str(cred_pres)
            if c_cp:
                _sub(g_ibscbs_el, "cCredPres", clean_digits(c_cp).zfill(2)[:2])

        trib_reg = reforma.get("tributacao_regular") or servico.get("tributacao_regular")
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
