"""Serviço de consulta às tabelas oficiais da NFS-e Nacional (Padrão ADN / Sefin Nacional v1.01).

Fornece acesso rápido em memória para:
1. Tabela completa de CST (18 códigos) e cClassTrib (138 classificações tributárias IBS/CBS da LC 214/2025).
2. Lista Nacional de Serviços (338 códigos cTribNac de 6 dígitos baseados na LC 116/2003 + regras de incidência).
3. Matriz de Correlação Oficial do Anexo VIII (1.739 combinações entre LC 116, cTribNac, NBS/cNBS, cIndOp e cClassTrib).
4. Tabela de Indicadores de Operação (cIndOp) e favoritos de emissão.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOGS_DIR = Path(__file__).resolve().parent / "catalogs"

_CLASS_TRIB_DATA: Dict[str, Any] = {"csts": [], "classificacoes": []}
_CLASS_TRIB_BY_CODE: Dict[str, Dict[str, Any]] = {}
_CST_BY_CODE: Dict[str, Dict[str, Any]] = {}
_SERVICOS_CTRIBNAC: List[Dict[str, Any]] = []
_SERVICO_BY_CODE: Dict[str, Dict[str, Any]] = {}
_CORRELACOES_ANEXO_VIII: List[Dict[str, Any]] = []
_INDOP_TABELA: List[Dict[str, Any]] = []
_INDOP_BY_CODE: Dict[str, Dict[str, Any]] = {}


def _load_catalogs() -> None:
    """Carrega os arquivos JSON de catálogo em memória na inicialização."""
    global _CLASS_TRIB_DATA, _CLASS_TRIB_BY_CODE, _CST_BY_CODE
    global _SERVICOS_CTRIBNAC, _SERVICO_BY_CODE
    global _CORRELACOES_ANEXO_VIII, _INDOP_TABELA, _INDOP_BY_CODE

    class_trib_path = CATALOGS_DIR / "class_trib_completa.json"
    if class_trib_path.exists():
        _CLASS_TRIB_DATA = json.loads(class_trib_path.read_text(encoding="utf-8"))
        _CLASS_TRIB_BY_CODE = {item["codigo"]: item for item in _CLASS_TRIB_DATA.get("classificacoes", [])}
        _CST_BY_CODE = {item["cst"]: item for item in _CLASS_TRIB_DATA.get("csts", [])}

    servicos_path = CATALOGS_DIR / "servicos_ctribnac.json"
    if servicos_path.exists():
        _SERVICOS_CTRIBNAC = json.loads(servicos_path.read_text(encoding="utf-8"))
        _SERVICO_BY_CODE = {item["cTribNac"]: item for item in _SERVICOS_CTRIBNAC}

    correlacoes_path = CATALOGS_DIR / "correlacao_anexo_viii.json"
    if correlacoes_path.exists():
        _CORRELACOES_ANEXO_VIII = json.loads(correlacoes_path.read_text(encoding="utf-8"))

    indop_path = CATALOGS_DIR / "indop_tabela.json"
    if indop_path.exists():
        _INDOP_TABELA = json.loads(indop_path.read_text(encoding="utf-8"))
        _INDOP_BY_CODE = {item["cIndOp"]: item for item in _INDOP_TABELA}


_load_catalogs()

CATALOGO_FAVORITOS: List[Dict[str, Any]] = [
    {
        "id": "ti_dev_software",
        "nome": "Desenvolvimento de Software Customizado",
        "item_lc116": "01.01",
        "cTribNac": "010101",
        "cNBS": "115022000",
        "nbs": "1.1502.20.00",
        "descricao_nbs": "Serviços de projeto e desenvolvimento, adaptação e instalação de aplicativos e programas personalizados (customizados)",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "000",
        "cClassTrib": "000001",
        "aliquota_iss_padrao": 2.0,
    },
    {
        "id": "ti_cloud_saas",
        "nome": "Hospedagem em Nuvem e Software como Serviço (SaaS)",
        "item_lc116": "01.03",
        "cTribNac": "010301",
        "cNBS": "115062100",
        "nbs": "1.1506.21.00",
        "descricao_nbs": "Serviços de hospedagem de aplicativos e programas software como serviço (SaaS)",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "000",
        "cClassTrib": "000001",
        "aliquota_iss_padrao": 2.5,
    },
    {
        "id": "ti_suporte",
        "nome": "Suporte Técnico e Gestão de TI",
        "item_lc116": "01.07",
        "cTribNac": "010701",
        "cNBS": "115013000",
        "nbs": "1.1501.30.00",
        "descricao_nbs": "Serviços de suporte em tecnologia da informação (TI)",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "000",
        "cClassTrib": "000001",
        "aliquota_iss_padrao": 3.0,
    },
    {
        "id": "consultoria_adm",
        "nome": "Consultoria em Gestão Empresarial",
        "item_lc116": "17.01",
        "cTribNac": "170101",
        "cNBS": "120011100",
        "nbs": "1.2001.11.00",
        "descricao_nbs": "Serviços de consultoria em gestão estratégica e empresarial",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "000",
        "cClassTrib": "000001",
        "aliquota_iss_padrao": 5.0,
    },
    {
        "id": "prof_juridico",
        "nome": "Serviços Advocatícios (Profissão Regulamentada - Redução 30%)",
        "item_lc116": "17.14",
        "cTribNac": "171401",
        "cNBS": "111011100",
        "nbs": "1.1101.11.00",
        "descricao_nbs": "Serviços de consultoria e representação jurídica",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "200",
        "cClassTrib": "200052",
        "aliquota_iss_padrao": 3.0,
    },
    {
        "id": "saude_medico",
        "nome": "Serviços Médicos Ambulatoriais (Saúde Humana - Redução 60%)",
        "item_lc116": "04.01",
        "cTribNac": "040101",
        "cNBS": "123012200",
        "nbs": "1.2301.22.00",
        "descricao_nbs": "Serviços médicos especializados",
        "indop": "100301",
        "local_incidencia": "Domicílio principal do adquirente",
        "cst": "200",
        "cClassTrib": "200029",
        "aliquota_iss_padrao": 2.0,
    },
]


def listar_cst(apenas_nfse: bool = False) -> List[Dict[str, Any]]:
    """Lista os Códigos de Situação Tributária (CST) do IBS/CBS."""
    csts = _CLASS_TRIB_DATA.get("csts", [])
    if not apenas_nfse:
        return csts

    filtrados = []
    for cst_obj in csts:
        classifs_nfse = [c for c in cst_obj.get("classificacoes", []) if c.get("ind_nfse") or c.get("ind_anexo_viii")]
        if classifs_nfse:
            copia = dict(cst_obj)
            copia["classificacoes"] = classifs_nfse
            filtrados.append(copia)
    return filtrados


def listar_cclasstrib(
    cst: Optional[str] = None,
    apenas_nfse: bool = False,
    apenas_anexo_viii: bool = False,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista ou filtra os 138 códigos cClassTrib da Reforma Tributária."""
    termo = (q or "").strip().lower()
    cst_norm = (cst or "").strip().zfill(3) if cst else None

    resultados = []
    for item in _CLASS_TRIB_DATA.get("classificacoes", []):
        if cst_norm and item.get("cst") != cst_norm:
            continue
        if apenas_nfse and not (item.get("ind_nfse") or item.get("ind_anexo_viii")):
            continue
        if apenas_anexo_viii and not item.get("ind_anexo_viii"):
            continue
        if termo:
            texto = f"{item.get('codigo', '')} {item.get('cst', '')} {item.get('nome', '')} {item.get('nome_reduzido', '')}".lower()
            if termo not in texto:
                continue
        resultados.append(item)
    return resultados


def obter_cclasstrib(codigo: str) -> Optional[Dict[str, Any]]:
    """Obtém os metadados completos de um código cClassTrib de 6 dígitos."""
    cod_norm = (codigo or "").strip().zfill(6)
    return _CLASS_TRIB_BY_CODE.get(cod_norm)


def obter_cst(cst: str) -> Optional[Dict[str, Any]]:
    """Obtém os metadados de um código CST de 3 dígitos."""
    cst_norm = (cst or "").strip().zfill(3)
    return _CST_BY_CODE.get(cst_norm)


def listar_servicos_ctribnac(
    item_lc116: Optional[str] = None,
    q: Optional[str] = None,
    limite: int = 400,
) -> List[Dict[str, Any]]:
    """Lista ou pesquisa os 338 códigos de serviço cTribNac (6 dígitos - LC 116/2003)."""
    termo = (q or "").strip().lower()
    lc_norm = (item_lc116 or "").strip()

    resultados = []
    for srv in _SERVICOS_CTRIBNAC:
        if lc_norm and srv.get("item_lc116") != lc_norm:
            continue
        if termo:
            texto = f"{srv.get('cTribNac', '')} {srv.get('item_lc116', '')} {srv.get('codigo_formatado', '')} {srv.get('descricao', '')}".lower()
            if termo not in texto:
                continue
        resultados.append(srv)
        if len(resultados) >= limite:
            break
    return resultados


def obter_servico_ctribnac(c_trib_nac: str) -> Optional[Dict[str, Any]]:
    """Retorna os detalhes de um código cTribNac (6 dígitos) e suas correlações do Anexo VIII."""
    cod_norm = "".join(ch for ch in (c_trib_nac or "") if ch.isdigit()).zfill(6)
    srv = _SERVICO_BY_CODE.get(cod_norm)
    if not srv:
        return None
    correlacoes = buscar_correlacoes_anexo_viii(c_trib_nac=cod_norm, limite=200)
    resultado = dict(srv)
    resultado["correlacoes_anexo_viii"] = correlacoes
    return resultado


def listar_subitens_lc116() -> List[Dict[str, Any]]:
    """Lista todos os subitens da LC 116/2003 com seus respectivos desdobramentos cTribNac."""
    agrupado: Dict[str, Dict[str, Any]] = {}
    for srv in _SERVICOS_CTRIBNAC:
        item_lc = srv["item_lc116"]
        if item_lc not in agrupado:
            agrupado[item_lc] = {
                "item_lc116": item_lc,
                "descricao": srv["descricao"],
                "codigos_cTribNac": [],
            }
        agrupado[item_lc]["codigos_cTribNac"].append(srv["cTribNac"])
    return sorted(agrupado.values(), key=lambda x: x["item_lc116"])


def buscar_correlacoes_anexo_viii(
    q: Optional[str] = None,
    item_lc116: Optional[str] = None,
    c_trib_nac: Optional[str] = None,
    c_nbs: Optional[str] = None,
    c_class_trib: Optional[str] = None,
    indop: Optional[str] = None,
    limite: int = 100,
) -> List[Dict[str, Any]]:
    """Pesquisa nas 1.739 correlações oficiais do Anexo VIII (LC 116 x NBS x INDOP x cClassTrib)."""
    termo = (q or "").strip().lower()
    lc_norm = (item_lc116 or "").strip()
    ctrib_norm = "".join(ch for ch in (c_trib_nac or "") if ch.isdigit()).zfill(6) if c_trib_nac else None
    nbs_norm = "".join(ch for ch in (c_nbs or "") if ch.isdigit()) if c_nbs else None
    cclass_norm = (c_class_trib or "").strip().zfill(6) if c_class_trib else None
    indop_norm = (indop or "").strip().zfill(6) if indop else None

    resultados = []
    for item in _CORRELACOES_ANEXO_VIII:
        if lc_norm and item.get("item_lc116") != lc_norm:
            continue
        if ctrib_norm:
            cods = item.get("codigos_cTribNac") or [item.get("cTribNac")]
            if ctrib_norm not in cods and item.get("item_lc116") != f"{ctrib_norm[:2]}.{ctrib_norm[2:4]}":
                continue
        if nbs_norm and nbs_norm not in (item.get("cNBS") or ""):
            continue
        if cclass_norm and item.get("cClassTrib") != cclass_norm:
            continue
        if indop_norm and item.get("indop") != indop_norm:
            continue
        if termo:
            comb = (
                f"{item.get('item_lc116', '')} {item.get('cTribNac', '')} "
                f"{item.get('descricao_lc116', '')} {item.get('nbs', '')} "
                f"{item.get('cNBS', '')} {item.get('descricao_nbs', '')} "
                f"{item.get('indop', '')} {item.get('cClassTrib', '')} "
                f"{item.get('nome_cClassTrib', '')}"
            ).lower()
            if termo not in comb:
                continue

        resultados.append(item)
        if len(resultados) >= limite:
            break
    return resultados


def listar_indop() -> List[Dict[str, Any]]:
    """Lista a tabela de Códigos Indicadores da Operação (cIndOp)."""
    return _INDOP_TABELA


def obter_indop(c_ind_op: str) -> Optional[Dict[str, Any]]:
    """Obtém metadados de um código indicador de operação (cIndOp)."""
    cod_norm = "".join(ch for ch in (c_ind_op or "") if ch.isdigit()).zfill(6)
    return _INDOP_BY_CODE.get(cod_norm)


def listar_favoritos() -> List[Dict[str, Any]]:
    """Retorna os templates favoritos de serviços mais utilizados."""
    return CATALOGO_FAVORITOS
