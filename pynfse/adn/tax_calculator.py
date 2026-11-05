"""Motor Tributário da NFS-e Nacional (ISSQN, Retenções Federais e IBS/CBS - Reforma Tributária).

Implementa as regras de cálculo e validação da Nota Técnica SE/CGNFS-e v1.01 (NT 1.101 / NT 007 / LC 214/2025):
- Regra E1530 (Base de Cálculo IBS/CBS vBC):
  * 2026 (01/01/2026 a 31/12/2026):
    vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN - vPIS - vCOFINS
  * 2027 a 2032 (01/01/2027 a 31/12/2032):
    vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN
  * 2033 em diante:
    vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS
- Regra E0958/E0959: Compatibilidade CST (3 dígitos) x cClassTrib (6 dígitos) e aplicação automática
  dos percentuais oficiais de redução de IBS (UF/Mun) e CBS (União).
- Regra E1555 (Valor Total da NFS-e vTotNF):
  * Em 2026: vTotNF = vLiq
  * A partir de 2027: vTotNF = vLiq + vCBS + vIBSTot
- Suporte a Diferimento (gDif), Crédito Presumido (gIBSCredPres/gCBSCredPres),
  Tributação Regular (gTribRegular), Compras Governamentais (gTribCompraGov) e Estorno de Crédito (gEstornoCred).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pynfse.adn.catalog_service import obter_cclasstrib, obter_indop, obter_servico_ctribnac


def _extrair_ano_competencia(data_competencia: Optional[str] = None, ano_competencia: Optional[int] = None) -> int:
    """Determina o ano de competência para aplicar a regra de transição correta (2026 vs 2027+)."""
    if ano_competencia and ano_competencia >= 2025:
        return int(ano_competencia)
    if data_competencia:
        limpo = data_competencia.strip()
        try:
            if "-" in limpo and len(limpo) >= 4:
                return int(limpo[:4])
            if "/" in limpo:
                partes = limpo.split("/")
                if len(partes[-1]) == 4:
                    return int(partes[-1])
        except ValueError:
            pass
    return datetime.now().year


def validar_regras_ibscbs(
    c_class_trib: str,
    cst: Optional[str] = None,
    c_ind_op: str = "100301",
    c_trib_nac: Optional[str] = None,
    c_nbs: Optional[str] = None,
    tp_oper: Optional[int] = None,
    tp_ente_gov: Optional[int] = None,
    p_redutor_gov: Optional[float] = None,
    ind_dest: int = 0,
    tem_destinatario: bool = False,
    tem_imovel: bool = False,
    tem_ref_nfse: bool = False,
    cst_reg: Optional[str] = None,
    c_class_trib_reg: Optional[str] = None,
    p_dif_uf: Optional[float] = None,
    p_dif_mun: Optional[float] = None,
    p_dif_cbs: Optional[float] = None,
    ind_doacao: Optional[int] = None,
    v_ibs_est_cred: Optional[float] = None,
    v_cbs_est_cred: Optional[float] = None,
) -> Dict[str, Any]:
    """Valida as regras de negócio de IBS/CBS da NT v1.01 (Anexo VI - RN DPS_NFS-e).

    Retorna dicionário com `valido: bool`, `erros: List[Dict]` e `avisos: List[Dict]`.
    """
    erros: List[Dict[str, str]] = []
    avisos: List[Dict[str, str]] = []

    cod_class = (c_class_trib or "").strip().zfill(6)
    ct_info = obter_cclasstrib(cod_class)
    if not ct_info:
        erros.append(
            {
                "codigo": "E0958",
                "mensagem": f"cClassTrib '{cod_class}' não encontrado na tabela oficial de classificação tributária.",
            }
        )
        return {"valido": False, "erros": erros, "avisos": avisos}

    if not (ct_info.get("ind_nfse") or ct_info.get("ind_anexo_viii")):
        avisos.append(
            {
                "codigo": "W0958",
                "mensagem": f"O cClassTrib '{cod_class}' possui IndNfse=False na tabela geral; verifique se é aplicável à operação.",
            }
        )

    cst_esperado = ct_info["cst"]
    cst_informado = (cst or cst_esperado).strip().zfill(3)
    if cst_informado != cod_class[:3] or cst_informado != cst_esperado:
        erros.append(
            {
                "codigo": "E0959",
                "mensagem": (
                    f"cClassTrib '{cod_class}' não pertence ao grupo CST '{cst_informado}'. "
                    f"Os 3 primeiros dígitos devem coincidir com o CST ('{cst_esperado}')."
                ),
            }
        )

    # Regra E0964 / E0965 - Tributação Regular
    exige_trib_reg = bool(ct_info.get("ind_trib_regular"))
    informou_trib_reg = bool(cst_reg or c_class_trib_reg)
    if exige_trib_reg and not informou_trib_reg:
        erros.append(
            {
                "codigo": "E0965",
                "mensagem": f"Grupo de tributação regular (gTribRegular) é obrigatório para o cClassTrib '{cod_class}'.",
            }
        )
    elif not exige_trib_reg and informou_trib_reg:
        erros.append(
            {
                "codigo": "E0964",
                "mensagem": f"Grupo de tributação regular (gTribRegular) não deve ser informado para o cClassTrib '{cod_class}'.",
            }
        )

    if informou_trib_reg and c_class_trib_reg:
        cod_reg = c_class_trib_reg.strip().zfill(6)
        ct_reg_info = obter_cclasstrib(cod_reg)
        if not ct_reg_info:
            erros.append(
                {
                    "codigo": "E0969",
                    "mensagem": f"cClassTribReg '{cod_reg}' inexistente na tabela oficial.",
                }
            )
        elif cst_reg and cst_reg.strip().zfill(3) != cod_reg[:3]:
            erros.append(
                {
                    "codigo": "E0970",
                    "mensagem": f"cClassTribReg '{cod_reg}' não pertence ao CSTReg '{cst_reg}'.",
                }
            )

    # Regra E0971 / E0972 - Diferimento (gDif)
    permite_dif = bool(ct_info.get("ind_diferimento"))
    informou_dif = any(v is not None and v > 0 for v in (p_dif_uf, p_dif_mun, p_dif_cbs))
    if informou_dif and not permite_dif:
        erros.append(
            {
                "codigo": "E0971",
                "mensagem": f"Grupo de diferimento (gDif) não é permitido para o cClassTrib '{cod_class}' (CST '{cst_esperado}').",
            }
        )
    elif permite_dif and not informou_dif:
        erros.append(
            {
                "codigo": "E0972",
                "mensagem": f"Grupo de diferimento (gDif) deve ser informado para o cClassTrib '{cod_class}' (CST '{cst_esperado}').",
            }
        )

    # Regra E1522 / E1523 - Compras Governamentais
    if tp_ente_gov is not None and (p_redutor_gov is None):
        avisos.append(
            {
                "codigo": "E1523",
                "mensagem": "Quando tpEnteGov é informado, o percentual redutor (pRedutor) de compras governamentais deve ser informado.",
            }
        )
    elif tp_ente_gov is None and p_redutor_gov is not None and p_redutor_gov > 0:
        erros.append(
            {
                "codigo": "E1522",
                "mensagem": "O percentual redutor para compras governamentais (pRedutor) não deve ser informado sem tpEnteGov.",
            }
        )

    # Regra E0905 / E0906 - gRefNFSe vs tpOper
    if tp_oper in (2, 3) and not tem_ref_nfse:
        erros.append(
            {
                "codigo": "E0905",
                "mensagem": f"O grupo de documentos referenciados (gRefNFSe) é obrigatório quando tpOper = {tp_oper}.",
            }
        )
    elif (tp_oper is None or tp_oper in (1, 4, 5)) and tem_ref_nfse:
        erros.append(
            {
                "codigo": "E0906",
                "mensagem": "O grupo de documentos referenciados (gRefNFSe) só pode ser informado quando tpOper = 2 ou 3.",
            }
        )

    # Regra E0910 - Destinatário vs indDest
    if ind_dest == 0 and tem_destinatario:
        erros.append(
            {
                "codigo": "E0910",
                "mensagem": "O grupo 'dest' (Destinatário) só deve ser informado quando indDest = 1.",
            }
        )

    # Regra E0931 / E0932 - Operações com Imóveis
    subitens_construcao = {
        "070201",
        "070202",
        "070401",
        "070501",
        "070502",
        "070601",
        "070602",
        "070701",
        "070801",
        "071701",
        "071901",
    }
    ctrib_limpo = "".join(ch for ch in (c_trib_nac or "") if ch.isdigit()).zfill(6) if c_trib_nac else ""
    indop_limpo = "".join(ch for ch in (c_ind_op or "") if ch.isdigit()).zfill(6)
    if ctrib_limpo in subitens_construcao and tem_imovel:
        erros.append(
            {
                "codigo": "E0931",
                "mensagem": "Não é permitido informar o grupo 'imovel' dentro de IBSCBS quando cTribNac é de construção civil (usar grupo obra do serviço).",
            }
        )
    elif ctrib_limpo not in subitens_construcao and indop_limpo in {"020101", "020201", "020301"} and not tem_imovel:
        avisos.append(
            {
                "codigo": "E0932",
                "mensagem": f"O grupo 'imovel' é exigido quando cIndOp = '{indop_limpo}' (operações com bens imóveis).",
            }
        )

    # Regra 566 / 666 - Doação e Estorno de Crédito (410003 / 410026)
    if cod_class in {"410003", "410026"} and ind_doacao is None:
        erros.append(
            {
                "codigo": "E0966",
                "mensagem": f"O indicador de doação (indDoacao) é obrigatório para o cClassTrib '{cod_class}'.",
            }
        )
    if cod_class == "410026" and ind_doacao is not None and (v_ibs_est_cred is None or v_cbs_est_cred is None):
        erros.append(
            {
                "codigo": "E0967",
                "mensagem": "O grupo de estorno de crédito (gEstornoCred) é obrigatório para cClassTrib 410026 com indDoacao.",
            }
        )

    return {"valido": len(erros) == 0, "erros": erros, "avisos": avisos}


def calcular_tributacao(
    valor_servicos: float,
    regime_prestador: str = "normal",
    cClassTrib: str = "000001",
    cst: Optional[str] = None,
    cIndOp: str = "100301",
    cTribNac: Optional[str] = None,
    cNBS: Optional[str] = None,
    data_competencia: Optional[str] = None,
    ano_competencia: Optional[int] = None,
    # Descontos, deduções e reembolsos
    desconto_incondicionado: float = 0.0,
    desconto_condicionado: float = 0.0,
    deducao_reducao_iss: float = 0.0,
    reembolso_repasse_ressarcimento: float = 0.0,
    deducao_reducao_ibscbs: float = 0.0,
    # ISSQN
    aliquota_iss_informada: Optional[float] = None,
    iss_retido: bool = False,
    tp_ret_issqn: Optional[int] = None,
    trib_issqn: int = 1,
    # Retenções e Tributos Federais (PIS/COFINS/IRRF/CSLL/INSS)
    reter_federais: bool = False,
    cst_pis_cofins: str = "01",
    p_aliq_pis: Optional[float] = None,
    p_aliq_cofins: Optional[float] = None,
    v_pis_informado: Optional[float] = None,
    v_cofins_informado: Optional[float] = None,
    tp_ret_pis_cofins: str = "2",
    v_irrf_informado: Optional[float] = None,
    v_csll_informado: Optional[float] = None,
    v_inss_informado: Optional[float] = None,
    # Alíquotas IBS / CBS
    p_ibs_uf: Optional[float] = None,
    p_ibs_mun: Optional[float] = None,
    p_cbs: Optional[float] = None,
    p_red_aliq_uf: Optional[float] = None,
    p_red_aliq_mun: Optional[float] = None,
    p_red_aliq_cbs: Optional[float] = None,
    # Compras Governamentais
    tp_ente_gov: Optional[int] = None,
    p_redutor_gov: Optional[float] = None,
    # Diferimento
    p_dif_uf: Optional[float] = None,
    p_dif_mun: Optional[float] = None,
    p_dif_cbs: Optional[float] = None,
    # Crédito Presumido
    c_cred_pres: Optional[str] = None,
    p_cred_pres_ibs: Optional[float] = None,
    p_cred_pres_cbs: Optional[float] = None,
    # Tributação Regular
    cst_reg: Optional[str] = None,
    c_class_trib_reg: Optional[str] = None,
    p_aliq_reg_ibs_uf: Optional[float] = None,
    p_aliq_reg_ibs_mun: Optional[float] = None,
    p_aliq_reg_cbs: Optional[float] = None,
    # Doação / Estorno de Crédito
    ind_doacao: Optional[int] = None,
    v_ibs_est_cred: Optional[float] = None,
    v_cbs_est_cred: Optional[float] = None,
    # Opção para apurar IBS/CBS no Simples Nacional (por fora / transferência de crédito)
    apurar_ibscbs_simples: bool = False,
    # Backwards-compatibility aliases
    aliquota_cbs_teste: Optional[float] = None,
    aliquota_ibs_teste: Optional[float] = None,
) -> Dict[str, Any]:
    """Calcula todos os tributos da NFS-e (ISSQN, Federais e IBS/CBS) segundo as regras da NT v1.01 (NT 1.101)."""
    v_serv = round(float(valor_servicos or 0.0), 2)
    v_desc_incond = round(float(desconto_incondicionado or 0.0), 2)
    v_desc_cond = round(float(desconto_condicionado or 0.0), 2)
    v_calc_dr = round(float(deducao_reducao_iss or 0.0), 2)
    v_ree_rep_res = round(float(reembolso_repasse_ressarcimento or 0.0), 2)
    v_ded_red_ibscbs = round(float(deducao_reducao_ibscbs or 0.0), 2)

    ano = _extrair_ano_competencia(data_competencia, ano_competencia)
    regime = (regime_prestador or "normal").strip().lower()

    # 1. Classificação Tributária (CST e cClassTrib)
    cod_class = (cClassTrib or "000001").strip().zfill(6)
    ct_info = obter_cclasstrib(cod_class) or {
        "codigo": cod_class,
        "cst": (cst or cod_class[:3]).zfill(3),
        "nome": "Classificação Tributária",
        "perc_red_ibs": 0.0,
        "perc_red_cbs": 0.0,
        "ind_exige_trib": True,
        "ind_trib_regular": False,
        "ind_permite_cred_pres": False,
        "ind_diferimento": False,
        "ind_reducao_aliq": False,
        "ind_reducao_bc": False,
        "ind_estorno_cred": False,
    }
    cst_final = (cst or ct_info.get("cst") or cod_class[:3]).strip().zfill(3)

    # 2. Cálculo do ISSQN (Regra 53 a 56 - RN DPS_NFS-e)
    v_bc_issqn = max(0.0, round(v_serv - v_desc_incond - v_calc_dr - v_ree_rep_res, 2))
    if regime == "mei":
        aliquota_iss = float(aliquota_iss_informada or 0.0)
    elif regime == "simples":
        aliquota_iss = float(aliquota_iss_informada if aliquota_iss_informada is not None else 2.0)
    else:
        aliquota_iss = float(aliquota_iss_informada if aliquota_iss_informada is not None else 5.0)

    # Limite constitucional de 5% (Regra E1300)
    aliquota_iss = min(max(aliquota_iss, 0.0), 5.0)

    if int(trib_issqn) == 1 and regime != "mei":
        v_issqn = round(v_bc_issqn * (aliquota_iss / 100.0), 2)
    else:
        v_issqn = 0.0

    tp_ret_iss_final = int(tp_ret_issqn) if tp_ret_issqn is not None else (2 if iss_retido else 1)
    is_iss_retido = tp_ret_iss_final in (2, 3) or bool(iss_retido)
    v_issqn_retido = v_issqn if is_iss_retido else 0.0

    # 3. Cálculo dos Tributos e Retenções Federais (PIS, COFINS, IRRF, CSLL, INSS)
    v_bc_pis_cofins = max(0.0, round(v_serv - v_desc_incond, 2))
    if v_pis_informado is not None or v_cofins_informado is not None:
        aliq_pis = float(p_aliq_pis or 0.65)
        aliq_cofins = float(p_aliq_cofins or 3.00)
        v_pis = round(float(v_pis_informado or 0.0), 2)
        v_cofins = round(float(v_cofins_informado or 0.0), 2)
        if reter_federais and tp_ret_pis_cofins == "2":
            tp_ret_pis_cofins = "1"
    elif p_aliq_pis is not None or p_aliq_cofins is not None:
        aliq_pis = float(p_aliq_pis or 0.0)
        aliq_cofins = float(p_aliq_cofins or 0.0)
        v_pis = round(v_bc_pis_cofins * (aliq_pis / 100.0), 2)
        v_cofins = round(v_bc_pis_cofins * (aliq_cofins / 100.0), 2)
        if reter_federais and tp_ret_pis_cofins == "2":
            tp_ret_pis_cofins = "1"
    elif regime == "normal" and reter_federais:
        aliq_pis = 0.65
        aliq_cofins = 3.00
        v_pis = round(v_bc_pis_cofins * (aliq_pis / 100.0), 2)
        v_cofins = round(v_bc_pis_cofins * (aliq_cofins / 100.0), 2)
        tp_ret_pis_cofins = "1"  # 1 = PIS/COFINS Retido
    else:
        aliq_pis = 0.0
        aliq_cofins = 0.0
        v_pis = 0.0
        v_cofins = 0.0

    if v_irrf_informado is not None:
        v_irrf = round(float(v_irrf_informado), 2)
    elif regime == "normal" and reter_federais:
        v_irrf = round(v_bc_pis_cofins * 0.015, 2)
    else:
        v_irrf = 0.0

    if v_csll_informado is not None:
        v_csll = round(float(v_csll_informado), 2)
    elif regime == "normal" and reter_federais:
        v_csll = round(v_bc_pis_cofins * 0.010, 2)
    else:
        v_csll = 0.0

    v_inss = round(float(v_inss_informado or 0.0), 2)

    # Na NT 008 v1.02 / RN DPS_NFS-e: tpRetPisCofins = 1 (Retido), 2 (Não Retido), 3 (PIS Retido/COFINS Não), 4 (COFINS Retido/PIS Não)
    if tp_ret_pis_cofins == "1" or reter_federais:
        v_ret_pis_cofins = round(v_pis + v_cofins, 2)
    elif tp_ret_pis_cofins == "3":
        v_ret_pis_cofins = v_pis
    elif tp_ret_pis_cofins == "4":
        v_ret_pis_cofins = v_cofins
    else:
        v_ret_pis_cofins = 0.0

    total_retencoes_federais = round(v_ret_pis_cofins + v_irrf + v_csll + v_inss, 2)
    v_total_ret = round(v_issqn_retido + total_retencoes_federais, 2)

    # Regra 58 (E1508): vLiq = vServ - vDescIncond - vDescCond - vTotalRet
    v_liq = max(0.0, round(v_serv - v_desc_incond - v_desc_cond - v_total_ret, 2))

    # 4. Base de Cálculo do IBS e da CBS (Regra 67 / E1530)
    # - 2026: vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN - vPIS - vCOFINS
    # - 2027..2032: vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN
    # - 2033+: vBC = vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS
    if ano <= 2026:
        v_bc_ibscbs = max(
            0.0,
            round(v_serv - v_desc_incond - v_ree_rep_res - v_ded_red_ibscbs - v_issqn - v_pis - v_cofins, 2),
        )
        regra_vbc_aplicada = "2026 (vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN - vPIS - vCOFINS)"
    elif ano <= 2032:
        v_bc_ibscbs = max(
            0.0,
            round(v_serv - v_desc_incond - v_ree_rep_res - v_ded_red_ibscbs - v_issqn, 2),
        )
        regra_vbc_aplicada = "2027-2032 (vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - vISSQN)"
    else:
        v_bc_ibscbs = max(
            0.0,
            round(v_serv - v_desc_incond - v_ree_rep_res - v_ded_red_ibscbs, 2),
        )
        regra_vbc_aplicada = "2033+ (vServ - descIncond - vCalcReeRepRes - vCalcDedRedIBSCBS)"

    # 5. Alíquotas Nominais e Reduções de Alíquota IBS (UF e Mun) e CBS (União)
    # Em 2026 (ano-teste da LC 214/2025): CBS = 0,90% e IBS = 0,10% (UF = 0,10%, Mun = 0,00% ou parametrizado)
    aliq_ibs_uf_nom = (
        float(p_ibs_uf)
        if p_ibs_uf is not None
        else (float(aliquota_ibs_teste) if aliquota_ibs_teste is not None else (0.10 if ano <= 2026 else 8.85))
    )
    aliq_ibs_mun_nom = float(p_ibs_mun) if p_ibs_mun is not None else (0.00 if ano <= 2026 else 8.85)
    aliq_cbs_nom = (
        float(p_cbs)
        if p_cbs is not None
        else (float(aliquota_cbs_teste) if aliquota_cbs_teste is not None else (0.90 if ano <= 2026 else 8.80))
    )

    # Reduções da tabela cClassTrib (em %, ex: 60.0, 30.0, 70.0, 100.0)
    red_ibs_catalogo = float(ct_info.get("perc_red_ibs") or 0.0)
    red_cbs_catalogo = float(ct_info.get("perc_red_cbs") or 0.0)

    # Se CST for de isenção/imunidade/não incidência (ex: 400, 410), redução efetiva é 100%
    exige_trib = bool(ct_info.get("ind_exige_trib", True)) and cst_final not in {"400", "410"}

    red_uf = float(p_red_aliq_uf) if p_red_aliq_uf is not None else red_ibs_catalogo
    red_mun = float(p_red_aliq_mun) if p_red_aliq_mun is not None else red_ibs_catalogo
    red_cbs = float(p_red_aliq_cbs) if p_red_aliq_cbs is not None else red_cbs_catalogo

    red_gov = float(p_redutor_gov or 0.0) if tp_ente_gov is not None else 0.0

    # Verifica se deve zerar para Simples Nacional / MEI (quando não opta por apurar IBS/CBS por fora)
    is_simples_dispensado = regime in ("simples", "mei") and not apurar_ibscbs_simples

    if not exige_trib or is_simples_dispensado:
        aliq_efet_uf = 0.0
        aliq_efet_mun = 0.0
        aliq_efet_cbs = 0.0
    else:
        aliq_efet_uf = round(aliq_ibs_uf_nom * (1.0 - red_uf / 100.0) * (1.0 - red_gov / 100.0), 4)
        aliq_efet_mun = round(aliq_ibs_mun_nom * (1.0 - red_mun / 100.0) * (1.0 - red_gov / 100.0), 4)
        aliq_efet_cbs = round(aliq_cbs_nom * (1.0 - red_cbs / 100.0) * (1.0 - red_gov / 100.0), 4)

    # Valores brutos de IBS UF, IBS Mun e CBS antes de diferimento
    v_ibs_uf_bruto = round(v_bc_ibscbs * (aliq_efet_uf / 100.0), 2)
    v_ibs_mun_bruto = round(v_bc_ibscbs * (aliq_efet_mun / 100.0), 2)
    v_cbs_bruto = round(v_bc_ibscbs * (aliq_efet_cbs / 100.0), 2)

    # 6. Diferimento (gDif - Regras 106-122)
    perc_dif_uf = float(p_dif_uf or 0.0)
    perc_dif_mun = float(p_dif_mun or 0.0)
    perc_dif_cbs = float(p_dif_cbs or 0.0)

    v_dif_uf = round(v_ibs_uf_bruto * (perc_dif_uf / 100.0), 2) if perc_dif_uf > 0 else 0.0
    v_dif_mun = round(v_ibs_mun_bruto * (perc_dif_mun / 100.0), 2) if perc_dif_mun > 0 else 0.0
    v_dif_cbs = round(v_cbs_bruto * (perc_dif_cbs / 100.0), 2) if perc_dif_cbs > 0 else 0.0

    v_ibs_uf = max(0.0, round(v_ibs_uf_bruto - v_dif_uf, 2))
    v_ibs_mun = max(0.0, round(v_ibs_mun_bruto - v_dif_mun, 2))
    v_ibs_tot = round(v_ibs_uf + v_ibs_mun, 2)
    v_cbs = max(0.0, round(v_cbs_bruto - v_dif_cbs, 2))

    # 7. Crédito Presumido (gIBSCredPres / gCBSCredPres - Regras 101-104 / 116-119)
    perc_cp_ibs = float(p_cred_pres_ibs or 0.0) if c_cred_pres else 0.0
    perc_cp_cbs = float(p_cred_pres_cbs or 0.0) if c_cred_pres else 0.0
    v_cred_pres_ibs = round(v_bc_ibscbs * (perc_cp_ibs / 100.0), 2) if c_cred_pres else 0.0
    v_cred_pres_cbs = round(v_bc_ibscbs * (perc_cp_cbs / 100.0), 2) if c_cred_pres else 0.0

    # 8. Tributação Regular (gTribRegular - Regras 124-131)
    g_trib_regular = None
    if ct_info.get("ind_trib_regular") or cst_reg or c_class_trib_reg:
        cod_reg = (c_class_trib_reg or "000001").strip().zfill(6)
        ct_reg = obter_cclasstrib(cod_reg) or {}
        red_reg_ibs = float(ct_reg.get("perc_red_ibs") or 0.0)
        red_reg_cbs = float(ct_reg.get("perc_red_cbs") or 0.0)

        aliq_reg_uf = (
            float(p_aliq_reg_ibs_uf)
            if p_aliq_reg_ibs_uf is not None
            else round(aliq_ibs_uf_nom * (1.0 - red_reg_ibs / 100.0), 4)
        )
        aliq_reg_mun = (
            float(p_aliq_reg_ibs_mun)
            if p_aliq_reg_ibs_mun is not None
            else round(aliq_ibs_mun_nom * (1.0 - red_reg_ibs / 100.0), 4)
        )
        aliq_reg_cbs = (
            float(p_aliq_reg_cbs)
            if p_aliq_reg_cbs is not None
            else round(aliq_cbs_nom * (1.0 - red_reg_cbs / 100.0), 4)
        )
        g_trib_regular = {
            "CSTReg": (cst_reg or cod_reg[:3]).zfill(3),
            "cClassTribReg": cod_reg,
            "pAliqEfeRegIBSUF": round(aliq_reg_uf, 2),
            "vTribRegIBSUF": round(v_bc_ibscbs * (aliq_reg_uf / 100.0), 2),
            "pAliqEfeRegIBSMun": round(aliq_reg_mun, 2),
            "vTribRegIBSMun": round(v_bc_ibscbs * (aliq_reg_mun / 100.0), 2),
            "pAliqEfeRegCBS": round(aliq_reg_cbs, 2),
            "vTribRegCBS": round(v_bc_ibscbs * (aliq_reg_cbs / 100.0), 2),
        }

    # 9. Compras Governamentais (gTribCompraGov - Regras 132-139)
    g_trib_compra_gov = None
    if tp_ente_gov is not None:
        g_trib_compra_gov = {
            "tpEnteGov": int(tp_ente_gov),
            "pRedutor": round(red_gov, 2),
            "pIBSUF": round(aliq_efet_uf, 2),
            "vIBSUF": v_ibs_uf,
            "pIBSMun": round(aliq_efet_mun, 2),
            "vIBSMun": v_ibs_mun,
            "pCBS": round(aliq_efet_cbs, 2),
            "vCBS": v_cbs,
        }

    # 10. Valor Total da NFS-e considerando impostos por fora (Regra 98 / E1555)
    # Em 2026: vTotNF = vLiq
    # A partir de 2027: vTotNF = vLiq + vCBS + vIBSTot
    if ano <= 2026:
        v_tot_nf = v_liq
    else:
        v_tot_nf = round(v_liq + v_cbs + v_ibs_tot, 2)

    validacao_regras = validar_regras_ibscbs(
        c_class_trib=cod_class,
        cst=cst_final,
        c_ind_op=cIndOp,
        c_trib_nac=cTribNac,
        c_nbs=cNBS,
        tp_ente_gov=tp_ente_gov,
        p_redutor_gov=p_redutor_gov,
        cst_reg=cst_reg,
        c_class_trib_reg=c_class_trib_reg,
        p_dif_uf=p_dif_uf,
        p_dif_mun=p_dif_mun,
        p_dif_cbs=p_dif_cbs,
        ind_doacao=ind_doacao,
        v_ibs_est_cred=v_ibs_est_cred,
        v_cbs_est_cred=v_cbs_est_cred,
    )

    indop_info = obter_indop(cIndOp) or {}
    srv_info = obter_servico_ctribnac(cTribNac) if cTribNac else None

    return {
        "ano_competencia": ano,
        "regime_prestador": regime,
        "valor_servicos": v_serv,
        "desconto_incondicionado": v_desc_incond,
        "desconto_condicionado": v_desc_cond,
        "reembolso_repasse_ressarcimento": v_ree_rep_res,
        "deducao_reducao_ibscbs": v_ded_red_ibscbs,
        "base_calculo": v_bc_issqn,
        "base_calculo_issqn": v_bc_issqn,
        "base_calculo_ibscbs": v_bc_ibscbs,
        "regra_vbc_ibscbs": regra_vbc_aplicada,
        "iss": {
            "trib_issqn": int(trib_issqn),
            "aliquota": round(aliquota_iss, 2),
            "valor": v_issqn,
            "retido": is_iss_retido,
            "tp_ret_issqn": tp_ret_iss_final,
            "valor_retido": v_issqn_retido,
        },
        "retencoes_federais": {
            "cst_pis_cofins": cst_pis_cofins,
            "base_calculo_pis_cofins": v_bc_pis_cofins,
            "aliquota_pis": round(aliq_pis, 2),
            "aliquota_cofins": round(aliq_cofins, 2),
            "pis": v_pis,
            "cofins": v_cofins,
            "tp_ret_pis_cofins": tp_ret_pis_cofins,
            "pis_cofins_retido": v_ret_pis_cofins,
            "csll": v_csll,
            "irrf": v_irrf,
            "inss": v_inss,
            "total": total_retencoes_federais,
        },
        "reforma_tributaria": {
            "cst": cst_final,
            "nome_cst": ct_info.get("nome_cst"),
            "cClassTrib": cod_class,
            "nome_cClassTrib": ct_info.get("nome"),
            "cIndOp": "".join(ch for ch in (cIndOp or "100301") if ch.isdigit()).zfill(6),
            "local_incidencia_ibs": indop_info.get("local_incidencia"),
            "vBC": v_bc_ibscbs,
            "vCalcReeRepRes": v_ree_rep_res,
            "vCalcDedRedIBSCBS": v_ded_red_ibscbs,
            "ibs_uf": {
                "pIBSUF": round(aliq_ibs_uf_nom, 2),
                "pRedAliqUF": round(red_uf, 2),
                "pAliqEfetUF": round(aliq_efet_uf, 2),
                "pDifUF": round(perc_dif_uf, 2),
                "vDifUF": v_dif_uf,
                "vIBSUF": v_ibs_uf,
            },
            "ibs_mun": {
                "pIBSMun": round(aliq_ibs_mun_nom, 2),
                "pRedAliqMun": round(red_mun, 2),
                "pAliqEfetMun": round(aliq_efet_mun, 2),
                "pDifMun": round(perc_dif_mun, 2),
                "vDifMun": v_dif_mun,
                "vIBSMun": v_ibs_mun,
            },
            "cbs": {
                "pCBS": round(aliq_cbs_nom, 2),
                "pRedAliqCBS": round(red_cbs, 2),
                "pAliqEfetCBS": round(aliq_efet_cbs, 2),
                "pDifCBS": round(perc_dif_cbs, 2),
                "vDifCBS": v_dif_cbs,
                "vCBS": v_cbs,
            },
            "credito_presumido": (
                {
                    "cCredPres": c_cred_pres,
                    "pCredPresIBS": round(perc_cp_ibs, 2),
                    "vCredPresIBS": v_cred_pres_ibs,
                    "pCredPresCBS": round(perc_cp_cbs, 2),
                    "vCredPresCBS": v_cred_pres_cbs,
                }
                if c_cred_pres
                else None
            ),
            "tributacao_regular": g_trib_regular,
            "compras_governamentais": g_trib_compra_gov,
            # Campos resumidos de compatibilidade
            "aliquota_cbs": round(aliq_efet_cbs, 2),
            "valor_cbs": v_cbs,
            "aliquota_ibs": round(aliq_efet_uf + aliq_efet_mun, 2),
            "valor_ibs": v_ibs_tot,
            "valor_ibs_uf": v_ibs_uf,
            "valor_ibs_mun": v_ibs_mun,
            "total_novos_tributos": round(v_cbs + v_ibs_tot, 2),
            "vTotNF": v_tot_nf,
        },
        "servico_info": (
            {
                "cTribNac": srv_info["cTribNac"],
                "descricao": srv_info["descricao"],
                "regra_incidencia_issqn": srv_info["regra_incidencia_issqn"],
            }
            if srv_info
            else None
        ),
        "total_retencoes": v_total_ret,
        "valor_liquido": v_liq,
        "valor_total_nf": v_tot_nf,
        "validacao_ibscbs": validacao_regras,
    }
