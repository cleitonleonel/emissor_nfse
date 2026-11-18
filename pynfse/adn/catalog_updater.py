"""Sincronizador oficial dos catálogos tributários da NFS-e Nacional e Reforma Tributária (IBS/CBS).

Consulta exclusivamente fontes governamentais oficiais:
1. API de Dados Abertos da Calculadora Oficial da Receita Federal (`piloto-cbs.tributos.gov.br`):
   - Versão da base (`versaoDb`, `dataVersaoDb`)
   - Situações Tributárias CST (`situacoes-tributarias/cbs-ibs`)
   - Classificações Tributárias cClassTrib (`classificacoes-tributarias/cbs-ibs`)
   - Lista oficial completa de NBS (`nbs/lista`)
   - Indicadores de operação NFS-e (`nfse/indicador-operacao`) e combinações válidas por NBS
2. Portal Nacional da NFS-e (`gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc`):
   - Planilha oficial mais recente do Anexo VIII (correlação LC 116 x NBS x INDOP x cClassTrib x COD_ATIV_SN)
   - Planilha oficial mais recente do Anexo VII (tabela completa de códigos cIndOp)
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import openpyxl
import requests

from pynfse.adn.catalog_service import (
    BUILTIN_CATALOGS_DIR,
    get_catalogs_dir,
    obter_metadados_catalogos,
    reload_catalogs,
)

logger = logging.getLogger(__name__)

DEFAULT_RFB_CALC_API_URL = "https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/api"
DEFAULT_NFSE_RTC_URL = "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc"

# Cabeçalho compatível com o WAF da Receita Federal para endpoints públicos JSON
_RFB_HEADERS = {
    "User-Agent": "curl/8.5.0",
    "Accept": "application/json",
}
_GOVBR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; pynfse/0.2)",
}


def _get_rfb_base_url() -> str:
    return (os.getenv("PYNFSE_RFB_CALC_API_URL") or DEFAULT_RFB_CALC_API_URL).strip().rstrip("/")


def _get_rtc_index_url() -> str:
    return (os.getenv("PYNFSE_NFSE_RTC_URL") or DEFAULT_NFSE_RTC_URL).strip()


def _clean_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _format_nbs_dotted(cnbs: str) -> str:
    d = _clean_digits(cnbs).zfill(9)
    return f"{d[0]}.{d[1:5]}.{d[5:7]}.{d[7:9]}"


def _version_sort_key(url: str) -> Tuple[int, ...]:
    nums = [int(n) for n in re.findall(r"\d+", Path(url).name)]
    return tuple(nums) if nums else (0,)


def _atomic_write_json(target: Path, data: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, target)


def _read_existing_or_builtin(dest_dir: Path, filename: str, default: Any) -> Any:
    for candidate in (dest_dir / filename, BUILTIN_CATALOGS_DIR / filename):
        if candidate.exists() and candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass
    return default


def _rfb_get_json(session: requests.Session, path: str, timeout: float = 20.0) -> Any:
    url = f"{_get_rfb_base_url()}{path}"
    resp = session.get(url, headers=_RFB_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _discover_rtc_excel_urls(session: requests.Session, timeout: float = 20.0) -> Dict[str, Optional[str]]:
    """Descobre na página oficial do Portal NFS-e os links `.xlsx` mais novos do Anexo VII e Anexo VIII."""
    rtc_url = _get_rtc_index_url()
    resp = session.get(rtc_url, headers=_GOVBR_HEADERS, timeout=timeout)
    resp.raise_for_status()
    hrefs = re.findall(r'href=["\']([^"\']+\.xlsx)["\']', resp.text, flags=re.IGNORECASE)
    abs_urls = [urljoin(rtc_url, h) for h in hrefs]

    anexo_viii_candidates = [
        u for u in abs_urls if re.search(r"anexo[_-]?viii", Path(u).name, flags=re.IGNORECASE)
    ]
    anexo_vii_candidates = [
        u for u in abs_urls if re.search(r"anexo[_-]?vii[-_]indop", Path(u).name, flags=re.IGNORECASE)
    ]

    anexo_viii_url = max(anexo_viii_candidates, key=_version_sort_key) if anexo_viii_candidates else None
    anexo_vii_url = max(anexo_vii_candidates, key=_version_sort_key) if anexo_vii_candidates else None
    return {"anexo_viii_url": anexo_viii_url, "anexo_vii_url": anexo_vii_url}


def _expand_merged_sheet_rows(ws: openpyxl.worksheet.worksheet.Worksheet) -> List[List[Any]]:
    """Converte uma planilha openpyxl em matriz propagando valores de células mescladas."""
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    grid: List[List[Any]] = [
        [ws.cell(r, c).value for c in range(1, max_col + 1)]
        for r in range(1, max_row + 1)
    ]
    for rng in ws.merged_cells.ranges:
        top_val = ws.cell(rng.min_row, rng.min_col).value
        for r in range(rng.min_row, rng.max_row + 1):
            for c in range(rng.min_col, rng.max_col + 1):
                if grid[r - 1][c - 1] is None:
                    grid[r - 1][c - 1] = top_val
    return grid


def _normalize_header(val: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(val or "").strip().lower()).strip("_")


def _parse_anexo_vii_xlsx(xlsx_bytes: bytes, existing_indop: List[Dict[str, Any]], rfb_indops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mescla o Anexo VII oficial (.xlsx) com os metadados da Calculadora RFB e flags existentes."""
    existing_map = {str(i.get("cIndOp") or "").zfill(6): i for i in existing_indop}
    rfb_map = {str(i.get("cIndOp") or "").zfill(6): i for i in rfb_indops}
    merged: Dict[str, Dict[str, Any]] = {}

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = _expand_merged_sheet_rows(ws)
    if rows:
        headers = [_normalize_header(h) for h in rows[0]]
        col_idx = {h: idx for idx, h in enumerate(headers) if h}
        for row in rows[1:]:
            raw_code = row[col_idx.get("c_digo_indop", col_idx.get("codigo_indop", 0))]
            digits = _clean_digits(raw_code)
            if len(digits) != 6:
                continue
            code = digits.zfill(6)
            prev = existing_map.get(code, {})
            rfb = rfb_map.get(code, {})

            def _cell(
                names: Tuple[str, ...],
                fallback: Any = None,
                current_row: Tuple[Any, ...] = row,
            ) -> Any:
                for n in names:
                    if n in col_idx and col_idx[n] < len(current_row):
                        v = current_row[col_idx[n]]
                        if v is not None and str(v).strip() != "":
                            return str(v).strip()
                return fallback

            loc_inc = (
                _cell(("nfselocincidibs",))
                or rfb.get("localIncidencia")
                or prev.get("local_incidencia")
                or _cell(("local_do_fornecimento_a_ser_identificado_no_dfe",))
                or "-"
            )
            if loc_inc == "-":
                loc_inc = rfb.get("localIncidencia") or prev.get("local_incidencia") or "-"

            tipo_op = _cell(("tipo_de_opera_o", "tipo_de_operacao")) or rfb.get("tipoOperacao") or ""
            merged[code] = {
                "cIndOp": code,
                "local_incidencia": loc_inc,
                "permite_zfm_alc": bool(prev.get("permite_zfm_alc", False)),
                "exige_imovel": bool(
                    prev.get("exige_imovel")
                    or "imóvel" in tipo_op.lower()
                    or "imovel" in tipo_op.lower()
                    or "imóvel" in str(loc_inc).lower()
                ),
                "tipo_operacao": tipo_op,
                "caracteristica": _cell(("caracter_stica_do_fornecimento", "caracteristica_do_fornecimento")) or "",
                "local_fornecimento": rfb.get("localFornecimento")
                or _cell(("local_do_fornecimento_a_ser_identificado_no_dfe",))
                or "",
                "dispositivo_legal": _cell(("dispositivo_legal_lc_214_2025",)) or "",
                "ind_nfse": _cell(("indnfse",)) == "S",
            }

    for code, rfb in rfb_map.items():
        if code not in merged:
            prev = existing_map.get(code, {})
            loc_inc = rfb.get("localIncidencia") or prev.get("local_incidencia") or "-"
            tipo_op = rfb.get("tipoOperacao") or ""
            merged[code] = {
                "cIndOp": code,
                "local_incidencia": loc_inc,
                "permite_zfm_alc": bool(prev.get("permite_zfm_alc", False)),
                "exige_imovel": bool(prev.get("exige_imovel") or "imóvel" in loc_inc.lower()),
                "tipo_operacao": tipo_op,
                "caracteristica": "",
                "local_fornecimento": rfb.get("localFornecimento") or "",
                "dispositivo_legal": "",
                "ind_nfse": True,
            }

    for code, prev in existing_map.items():
        if code not in merged:
            merged[code] = prev

    return [merged[k] for k in sorted(merged)]


def _build_class_trib_data(
    rfb_csts: List[Dict[str, Any]],
    rfb_classifs: List[Dict[str, Any]],
    existing_data: Dict[str, Any],
    anexo_viii_codes: set[str],
) -> Dict[str, Any]:
    """Mescla CST e cClassTrib da API RFB preservando flags e nomes reduzidos existentes."""
    prev_cst_map = {item["cst"]: item for item in existing_data.get("csts", []) if item.get("cst")}
    prev_ct_map = {item["codigo"]: item for item in existing_data.get("classificacoes", []) if item.get("codigo")}

    cst_name_map: Dict[str, str] = {}
    cst_meta_map: Dict[str, Dict[str, Any]] = {}
    for c in rfb_csts:
        # Formato de situacoes-tributarias/cbs-ibs ou fallback do existente
        cst_code = _clean_digits(c.get("codigo") or c.get("cst") or "")
        if not cst_code and c.get("classificacoesTributarias"):
            first_ct = str(c["classificacoesTributarias"][0].get("codigo") or "")
            if len(first_ct) >= 3:
                cst_code = first_ct[:3]
        if not cst_code:
            continue
        cst_code = cst_code.zfill(3)
        prev = prev_cst_map.get(cst_code, {})
        cst_name = c.get("descricao") or prev.get("nome") or f"CST {cst_code}"
        cst_name_map[cst_code] = cst_name
        cst_meta_map[cst_code] = {
            "cst": cst_code,
            "nome": cst_name,
            "ind_exige_trib": bool(prev.get("ind_exige_trib", cst_code not in {"400", "410"})),
            "ind_reducao_aliq": bool(prev.get("ind_reducao_aliq", cst_code in {"200", "220"})),
            "ind_diferimento": bool(prev.get("ind_diferimento", cst_code in {"510", "515", "550"})),
            "ind_reducao_bc": bool(prev.get("ind_reducao_bc", False)),
            "ind_monofasica": bool(prev.get("ind_monofasica", cst_code == "620")),
            "ind_transferencia_cred": bool(prev.get("ind_transferencia_cred", False)),
            "ind_ajuste_compet": bool(prev.get("ind_ajuste_compet", False)),
            "classificacoes": [],
        }

    for cst_code, prev in prev_cst_map.items():
        if cst_code not in cst_meta_map:
            cst_name_map[cst_code] = prev.get("nome") or f"CST {cst_code}"
            cst_meta_map[cst_code] = {**prev, "classificacoes": []}

    classificacoes_by_code: Dict[str, Dict[str, Any]] = {}
    for item in rfb_classifs:
        cod = str(item.get("codigo") or "").strip().zfill(6)
        if not cod or cod == "000000":
            continue
        cst_code = cod[:3]
        prev = prev_ct_map.get(cod, {})
        siglas = {str(d.get("sigla") or "").upper() for d in (item.get("tiposDfeClassificacao") or [])}
        ind_nfse = ("NFS-E" in siglas or "NFSE" in siglas) if siglas else bool(prev.get("ind_nfse", False))
        if cod in anexo_viii_codes:
            ind_nfse = True

        red_ibs = float(
            item.get("percentualReducaoIbsMun")
            if item.get("percentualReducaoIbsMun") is not None
            else (item.get("percentualReducaoIbsUf") or prev.get("perc_red_ibs") or 0.0)
        )
        red_cbs = float(
            item.get("percentualReducaoCbs")
            if item.get("percentualReducaoCbs") is not None
            else (prev.get("perc_red_cbs") or 0.0)
        )

        nome_full = str(item.get("descricao") or prev.get("nome") or f"Classificação {cod}").strip()
        nome_red = str(
            prev.get("nome_reduzido") or item.get("descricaoTratamentoTributario") or nome_full[:80]
        ).strip()

        obj = {
            "codigo": cod,
            "cst": cst_code,
            "nome_cst": cst_name_map.get(cst_code) or prev.get("nome_cst") or f"CST {cst_code}",
            "nome": nome_full,
            "nome_reduzido": nome_red,
            "perc_red_ibs": red_ibs,
            "perc_red_cbs": red_cbs,
            "ind_exige_trib": bool(prev.get("ind_exige_trib", cst_code not in {"400", "410"})),
            "ind_trib_regular": bool(prev.get("ind_trib_regular", False)),
            "ind_permite_cred_pres": bool(
                item.get("indicaCreditoPresumidoFornecedor")
                or item.get("indicaCreditoPresumidoAdquirente")
                or prev.get("ind_permite_cred_pres", False)
            ),
            "ind_diferimento": bool(prev.get("ind_diferimento", cst_code in {"510", "515", "550"})),
            "ind_reducao_aliq": bool(red_ibs > 0 or red_cbs > 0 or prev.get("ind_reducao_aliq", False)),
            "ind_reducao_bc": bool(prev.get("ind_reducao_bc", False)),
            "ind_estorno_cred": bool(prev.get("ind_estorno_cred", False)),
            "ind_monofasica": bool(prev.get("ind_monofasica", cst_code == "620")),
            "ind_nfse": ind_nfse,
            "ind_anexo_viii": bool(cod in anexo_viii_codes or prev.get("ind_anexo_viii", False)),
            "ind_nfe": ("NF-E" in siglas) if siglas else bool(prev.get("ind_nfe", False)),
            "ind_nfce": ("NFC-E" in siglas) if siglas else bool(prev.get("ind_nfce", False)),
            "ind_cte": ("CT-E" in siglas) if siglas else bool(prev.get("ind_cte", False)),
            "ind_nfcom": ("NFCOM" in siglas) if siglas else bool(prev.get("ind_nfcom", False)),
            "nro_anexo": prev.get("nro_anexo"),
            "url_legislacao": prev.get("url_legislacao"),
            "tipo_aliq": item.get("tipoAliquota") or prev.get("tipo_aliq") or "Padrão",
            "dth_ini_vig": prev.get("dth_ini_vig"),
            "dth_fim_vig": prev.get("dth_fim_vig"),
        }
        classificacoes_by_code[cod] = obj

    for cod, prev in prev_ct_map.items():
        if cod not in classificacoes_by_code:
            classificacoes_by_code[cod] = prev

    sorted_classifs = [classificacoes_by_code[k] for k in sorted(classificacoes_by_code)]
    for item in sorted_classifs:
        cst_code = item["cst"]
        if cst_code not in cst_meta_map:
            cst_meta_map[cst_code] = {
                "cst": cst_code,
                "nome": item.get("nome_cst") or f"CST {cst_code}",
                "ind_exige_trib": True,
                "ind_reducao_aliq": False,
                "ind_diferimento": False,
                "ind_reducao_bc": False,
                "ind_monofasica": False,
                "ind_transferencia_cred": False,
                "ind_ajuste_compet": False,
                "classificacoes": [],
            }
        cst_meta_map[cst_code]["classificacoes"].append(item)

    sorted_csts = [cst_meta_map[k] for k in sorted(cst_meta_map)]
    return {"csts": sorted_csts, "classificacoes": sorted_classifs}


def _parse_anexo_viii_xlsx(
    xlsx_bytes: bytes,
    servicos_ctribnac: List[Dict[str, Any]],
    class_trib_by_code: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extrai correlações oficiais do Anexo VIII (.xlsx) expandindo células mescladas."""
    ctrib_by_lc: Dict[str, List[str]] = {}
    for srv in servicos_ctribnac:
        lc = str(srv.get("item_lc116") or "").strip()
        cod = str(srv.get("cTribNac") or "").strip()
        if lc and cod:
            ctrib_by_lc.setdefault(lc, []).append(cod)

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    sheet_name = "tabela geral" if "tabela geral" in wb.sheetnames else wb.sheetnames[0]
    rows = _expand_merged_sheet_rows(wb[sheet_name])
    if not rows:
        return []

    headers = [_normalize_header(h) for h in rows[0]]
    col_idx = {h: idx for idx, h in enumerate(headers) if h}

    def _val(row: List[Any], names: Tuple[str, ...], default_idx: Optional[int] = None) -> str:
        for n in names:
            if n in col_idx and col_idx[n] < len(row):
                v = row[col_idx[n]]
                return "" if v is None else str(v).strip()
        if default_idx is not None and default_idx < len(row) and row[default_idx] is not None:
            return str(row[default_idx]).strip()
        return ""

    correlacoes: List[Dict[str, Any]] = []
    seen = set()
    for row in rows[1:]:
        item_lc = _val(row, ("item_lc_116", "item_lc116"), 0)
        nbs_raw = _val(row, ("nbs",), 2)
        cnbs = _clean_digits(nbs_raw)
        if not item_lc or len(cnbs) < 7:
            continue
        cnbs = cnbs.zfill(9)
        nbs_fmt = nbs_raw if "." in nbs_raw else _format_nbs_dotted(cnbs)
        indop = _clean_digits(_val(row, ("indop", "cindop"), 6)).zfill(6)
        cclasstrib = _clean_digits(_val(row, ("cclasstrib",), 8)).zfill(6)
        if indop == "000000" or cclasstrib == "000000":
            continue

        dedup_key = (item_lc, cnbs, indop, cclasstrib)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        codigos_ctrib = ctrib_by_lc.get(item_lc, [])
        ct_meta = class_trib_by_code.get(cclasstrib, {})
        cst = str(ct_meta.get("cst") or cclasstrib[:3]).zfill(3)

        correlacoes.append(
            {
                "id": f"rec_{len(correlacoes) + 1}",
                "item_lc116": item_lc,
                "cTribNac": codigos_ctrib[0] if codigos_ctrib else "",
                "codigos_cTribNac": codigos_ctrib,
                "descricao_lc116": _val(row, ("descri_o_item", "descricao_item"), 1),
                "nbs": nbs_fmt,
                "cNBS": cnbs,
                "descricao_nbs": _val(row, ("descri_o_nbs", "descricao_nbs"), 3),
                "cod_ativ_sn": _val(row, ("cod_ativ_sn",), 4) or None,
                "ps_onerosa": "S",
                "adq_exterior": "N",
                "indop": indop,
                "local_incidencia_ibs": _val(row, ("local_incid_ncia_ibs", "local_incidencia_ibs"), 7),
                "cst": cst,
                "cClassTrib": cclasstrib,
                "nome_cClassTrib": _val(row, ("nome_cclasstrib",), 9) or ct_meta.get("nome") or "",
                "perc_red_ibs": float(ct_meta.get("perc_red_ibs") or 0.0),
                "perc_red_cbs": float(ct_meta.get("perc_red_cbs") or 0.0),
                "fonte": "anexo_viii",
            }
        )
    return correlacoes


def _query_rfb_nbs_combinations(
    nbs_list: List[Dict[str, Any]],
    ref_date: str,
    max_workers: int = 2,
) -> Dict[str, List[Dict[str, str]]]:
    """Consulta combinações (cClassTrib, cIndOp) aceitas pela Calculadora RFB com proteção contra WAF."""
    base = _get_rfb_base_url()
    results: Dict[str, List[Dict[str, str]]] = {}
    waf_blocked = False

    def _fetch_one(cnbs: str) -> Tuple[str, List[Dict[str, str]], bool]:
        combos: List[Dict[str, str]] = []
        if waf_blocked:
            return cnbs, combos, True
        try:
            with requests.Session() as sess:
                r1 = sess.get(
                    f"{base}/calculadora/nfse/situacoes-classificacoes-tributarias",
                    params={"nbs": cnbs, "data": ref_date},
                    headers={**_RFB_HEADERS, "Connection": "close"},
                    timeout=15.0,
                )
                if "Request Rejected" in r1.text:
                    return cnbs, combos, True
                if r1.status_code != 200 or not r1.text.strip().startswith("["):
                    return cnbs, combos, False
                cts = r1.json()
                for ct_obj in cts:
                    ct_code = str(ct_obj.get("codigoClassificacaoTributaria") or "").strip().zfill(6)
                    cst_code = str(ct_obj.get("codigoSituacaoTributaria") or ct_code[:3]).strip().zfill(3)
                    if not ct_code or ct_code == "000000":
                        continue
                    r2 = sess.get(
                        f"{base}/calculadora/nfse/indicador-operacao",
                        params={"nbs": cnbs, "cClassTrib": ct_code, "dataOcorrenciaFatoGerador": ref_date},
                        headers={**_RFB_HEADERS, "Connection": "close"},
                        timeout=15.0,
                    )
                    if "Request Rejected" in r2.text:
                        return cnbs, combos, True
                    if r2.status_code == 200 and r2.text.strip().startswith("["):
                        for op in r2.json():
                            indop = str(op.get("cIndOp") or "").strip().zfill(6)
                            if indop and indop != "000000":
                                combos.append(
                                    {
                                        "cClassTrib": ct_code,
                                        "cIndOp": indop,
                                        "cst": cst_code,
                                        "fonte": "calculadora",
                                    }
                                )
        except Exception as exc:
            logger.debug("Aviso ao consultar calculadora RFB para NBS %s: %s", cnbs, exc)
        return cnbs, combos, False

    codes = [_clean_digits(item.get("codigo")).zfill(9) for item in nbs_list if item.get("codigo")]
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 2))) as pool:
        futures = [pool.submit(_fetch_one, code) for code in codes]
        for fut in as_completed(futures):
            cnbs, combos, blocked = fut.result()
            if blocked:
                waf_blocked = True
            if combos:
                results[cnbs] = combos
    return results


def _build_nbs_catalog(
    rfb_nbs_list: List[Dict[str, Any]],
    correlacoes: List[Dict[str, Any]],
    calc_combos_by_nbs: Dict[str, List[Dict[str, str]]],
) -> List[Dict[str, Any]]:
    """Consolida os 920+ NBS oficiais com correlações do Anexo VIII e validação da Calculadora RFB."""
    corr_by_nbs: Dict[str, List[Dict[str, Any]]] = {}
    for corr in correlacoes:
        cnbs = _clean_digits(corr.get("cNBS")).zfill(9)
        if cnbs and cnbs != "000000000":
            corr_by_nbs.setdefault(cnbs, []).append(corr)

    desc_by_nbs: Dict[str, str] = {}
    for item in rfb_nbs_list:
        cnbs = _clean_digits(item.get("codigo")).zfill(9)
        if cnbs and cnbs != "000000000":
            desc_by_nbs[cnbs] = str(item.get("descricao") or "").strip()

    all_codes = sorted(set(desc_by_nbs.keys()) | set(corr_by_nbs.keys()))
    nbs_catalog: List[Dict[str, Any]] = []

    for cnbs in all_codes:
        corrs = corr_by_nbs.get(cnbs, [])
        calc_combos = calc_combos_by_nbs.get(cnbs, [])
        itens_lc116: List[str] = []
        codigos_ctrib: List[str] = []
        anexo_combos: List[Dict[str, str]] = []

        for corr in corrs:
            lc = corr.get("item_lc116")
            if lc and lc not in itens_lc116:
                itens_lc116.append(lc)
            for ctrib in corr.get("codigos_cTribNac") or ([corr.get("cTribNac")] if corr.get("cTribNac") else []):
                if ctrib and ctrib not in codigos_ctrib:
                    codigos_ctrib.append(ctrib)
            anexo_combos.append(
                {
                    "cClassTrib": str(corr.get("cClassTrib") or "").zfill(6),
                    "cIndOp": str(corr.get("indop") or "").zfill(6),
                    "cst": str(corr.get("cst") or "").zfill(3),
                    "fonte": "anexo_viii",
                }
            )

        # Mescla combinações da calculadora oficial + Anexo VIII (priorizando fonte calculadora)
        merged_combos: Dict[Tuple[str, str], Dict[str, str]] = {}
        for c in anexo_combos:
            merged_combos[(c["cClassTrib"], c["cIndOp"])] = c
        for c in calc_combos:
            key = (c["cClassTrib"], c["cIndOp"])
            if key in merged_combos:
                merged_combos[key]["fonte"] = "calculadora+anexo_viii"
            else:
                merged_combos[key] = c

        if not merged_combos:
            merged_combos[("000001", "100301")] = {
                "cClassTrib": "000001",
                "cIndOp": "100301",
                "cst": "000",
                "fonte": "regra_geral",
            }

        fonte = "calculadora" if calc_combos else ("anexo_viii" if corrs else "regra_geral")
        descricao = desc_by_nbs.get(cnbs) or (corrs[0].get("descricao_nbs") if corrs else "") or ""

        nbs_catalog.append(
            {
                "cNBS": cnbs,
                "nbs": _format_nbs_dotted(cnbs),
                "descricao": descricao,
                "itens_lc116": itens_lc116,
                "codigos_cTribNac": codigos_ctrib,
                "no_anexo_viii": bool(corrs),
                "fonte": fonte,
                "combinacoes": sorted(merged_combos.values(), key=lambda x: (x["cClassTrib"], x["cIndOp"])),
            }
        )
    return nbs_catalog


def verificar_atualizacao_oficial(timeout: float = 15.0) -> Dict[str, Any]:
    """Consulta a versão remota na API da Receita Federal e os links do Portal NFS-e sem baixar tudo."""
    atual = obter_metadados_catalogos()
    with requests.Session() as sess:
        versao_info = _rfb_get_json(sess, "/calculadora/dados-abertos/versao", timeout=timeout)
        rtc_links = _discover_rtc_excel_urls(sess, timeout=timeout)

    remota_db = str(versao_info.get("versaoDb") or "").strip()
    remota_a8 = rtc_links.get("anexo_viii_url")
    remota_a7 = rtc_links.get("anexo_vii_url")

    atualizacao_disponivel = (
        remota_db != atual.get("versao_db")
        or (remota_a8 and remota_a8 != atual.get("anexo_viii_url"))
        or (remota_a7 and remota_a7 != atual.get("anexo_vii_url"))
    )
    return {
        "atualizacao_disponivel": bool(atualizacao_disponivel),
        "versao_local": atual.get("versao_db"),
        "versao_remota": remota_db,
        "data_versao_remota": versao_info.get("dataVersaoDb"),
        "descricao_remota": versao_info.get("descricaoVersaoDb"),
        "anexo_viii_url": remota_a8,
        "anexo_vii_url": remota_a7,
    }


def atualizar_catalogos_oficiais(
    destino_dir: Optional[Path | str] = None,
    force: bool = False,
    validar_calculadora: bool = False,
    max_workers: int = 2,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Baixa e atualiza os catálogos oficiais a partir da Receita Federal e Portal NFS-e (gov.br)."""
    target_dir = Path(destino_dir).expanduser() if destino_dir else get_catalogs_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    ref_date = dt.date.today().isoformat()

    with requests.Session() as sess:
        versao_info = _rfb_get_json(sess, "/calculadora/dados-abertos/versao", timeout=timeout)
        rtc_links = _discover_rtc_excel_urls(sess, timeout=timeout)

        meta_atual = _read_existing_or_builtin(target_dir, "catalog_metadata.json", {})
        remota_db = str(versao_info.get("versaoDb") or "").strip()
        a8_url = rtc_links.get("anexo_viii_url")
        a7_url = rtc_links.get("anexo_vii_url")

        if (
            not force
            and meta_atual.get("versao_db") == remota_db
            and (not a8_url or meta_atual.get("anexo_viii_url") == a8_url)
            and (not a7_url or meta_atual.get("anexo_vii_url") == a7_url)
            and (target_dir / "nbs_tabela.json").exists()
        ):
            return {
                "atualizado": False,
                "motivo": f"Catálogos já estão na versão oficial mais recente ({remota_db}).",
                "metadados": obter_metadados_catalogos(),
            }

        rfb_csts = _rfb_get_json(sess, f"/calculadora/dados-abertos/situacoes-tributarias/cbs-ibs?data={ref_date}", timeout=timeout)
        rfb_classifs = _rfb_get_json(sess, f"/calculadora/dados-abertos/classificacoes-tributarias/cbs-ibs?data={ref_date}", timeout=timeout)
        rfb_nbs = _rfb_get_json(sess, f"/calculadora/dados-abertos/nbs/lista?data={ref_date}", timeout=timeout)
        rfb_indops = _rfb_get_json(sess, f"/calculadora/nfse/indicador-operacao?dataOcorrenciaFatoGerador={ref_date}", timeout=timeout)

        a8_bytes = sess.get(a8_url, headers=_GOVBR_HEADERS, timeout=timeout).content if a8_url else b""
        a7_bytes = sess.get(a7_url, headers=_GOVBR_HEADERS, timeout=timeout).content if a7_url else b""

    existing_ct = _read_existing_or_builtin(target_dir, "class_trib_completa.json", {"csts": [], "classificacoes": []})
    existing_servicos = _read_existing_or_builtin(target_dir, "servicos_ctribnac.json", [])
    existing_indop = _read_existing_or_builtin(target_dir, "indop_tabela.json", [])
    existing_corrs = _read_existing_or_builtin(target_dir, "correlacao_anexo_viii.json", [])

    # 1. Anexo VII / cIndOp
    if a7_bytes:
        indop_tabela = _parse_anexo_vii_xlsx(a7_bytes, existing_indop, rfb_indops)
    else:
        indop_tabela = existing_indop

    # 2. Anexo VIII preliminar para saber códigos do Anexo VIII antes de montar class_trib
    prelim_ct_map = {item["codigo"]: item for item in existing_ct.get("classificacoes", []) if item.get("codigo")}
    if a8_bytes:
        correlacoes_raw = _parse_anexo_viii_xlsx(a8_bytes, existing_servicos, prelim_ct_map)
    else:
        correlacoes_raw = existing_corrs

    anexo_viii_codes = {str(c.get("cClassTrib") or "").zfill(6) for c in correlacoes_raw if c.get("cClassTrib")}

    # 3. Tabela CST e cClassTrib
    class_trib_data = _build_class_trib_data(rfb_csts, rfb_classifs, existing_ct, anexo_viii_codes)
    ct_by_code = {item["codigo"]: item for item in class_trib_data.get("classificacoes", [])}

    # Re-enriquece perc_red_ibs/perc_red_cbs/cst nas correlações com os dados atualizados
    for corr in correlacoes_raw:
        meta = ct_by_code.get(str(corr.get("cClassTrib") or "").zfill(6))
        if meta:
            corr["cst"] = meta["cst"]
            corr["perc_red_ibs"] = meta["perc_red_ibs"]
            corr["perc_red_cbs"] = meta["perc_red_cbs"]

    # 4. Validação das combinações na Calculadora Oficial RFB (opcional e paralela)
    calc_combos_by_nbs: Dict[str, List[Dict[str, str]]] = {}
    if validar_calculadora and rfb_nbs:
        calc_combos_by_nbs = _query_rfb_nbs_combinations(rfb_nbs, ref_date=ref_date, max_workers=max_workers)

    # 5. Tabela completa de NBS (920+)
    nbs_tabela = _build_nbs_catalog(rfb_nbs, correlacoes_raw, calc_combos_by_nbs)

    metadata = {
        "versao_db": remota_db,
        "data_versao_db": versao_info.get("dataVersaoDb"),
        "descricao_versao_db": versao_info.get("descricaoVersaoDb"),
        "anexo_viii_versao": Path(a8_url).name if a8_url else meta_atual.get("anexo_viii_versao"),
        "anexo_vii_versao": Path(a7_url).name if a7_url else meta_atual.get("anexo_vii_versao"),
        "anexo_viii_url": a8_url,
        "anexo_vii_url": a7_url,
        "atualizado_em": dt.datetime.now(dt.UTC).isoformat(),
        "fontes": [
            f"{_get_rfb_base_url()} (Calculadora Oficial IBS/CBS Receita Federal)",
            f"{_get_rtc_index_url()} (Portal Nacional NFS-e - Anexos VII e VIII)",
        ],
        "calculadora_validada": bool(validar_calculadora and calc_combos_by_nbs),
    }

    _atomic_write_json(target_dir / "class_trib_completa.json", class_trib_data)
    _atomic_write_json(target_dir / "servicos_ctribnac.json", existing_servicos)
    _atomic_write_json(target_dir / "indop_tabela.json", indop_tabela)
    _atomic_write_json(target_dir / "correlacao_anexo_viii.json", correlacoes_raw)
    _atomic_write_json(target_dir / "nbs_tabela.json", nbs_tabela)
    _atomic_write_json(target_dir / "catalog_metadata.json", metadata)

    metadados_recarregados = reload_catalogs()
    return {
        "atualizado": True,
        "motivo": f"Catálogos atualizados para base oficial {remota_db}.",
        "metadados": metadados_recarregados,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza os catálogos fiscais do pynfse direto das fontes oficiais.")
    parser.add_argument("--dest", default=None, help="Diretório destino (padrão: get_catalogs_dir()).")
    parser.add_argument("--force", action="store_true", help="Força re-download mesmo se a versão for igual.")
    parser.add_argument("--calc", action="store_true", help="Consulta combinações individuais por NBS na calculadora RFB.")
    args = parser.parse_args(argv)

    res = atualizar_catalogos_oficiais(
        destino_dir=args.dest,
        force=args.force,
        validar_calculadora=args.calc,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
