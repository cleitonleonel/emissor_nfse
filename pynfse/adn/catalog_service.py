"""Serviço de consulta às tabelas oficiais da NFS-e Nacional (Padrão ADN / Sefin Nacional v1.01).

Fornece acesso rápido em memória com suporte a diretório externo atualizável (`PYNFSE_CATALOGS_DIR`
ou `set_catalogs_dir`) e fallback automático para os catálogos embarcados no pacote:
1. Tabela completa de CST (18 códigos) e cClassTrib (classificações tributárias IBS/CBS da LC 214/2025).
2. Lista Nacional de Serviços (338 códigos cTribNac de 6 dígitos baseados na LC 116/2003 + regras de incidência).
3. Matriz de Correlação Oficial do Anexo VIII (LC 116, cTribNac, NBS/cNBS, cIndOp e cClassTrib).
4. Tabela de Indicadores de Operação (cIndOp — Anexo VII + Calculadora Oficial RFB).
5. Catálogo completo de NBS (920+ códigos) com combinações validadas pela Calculadora Oficial e Anexo VIII.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

BUILTIN_CATALOGS_DIR = Path(__file__).resolve().parent / "catalogs"
CATALOGS_DIR = BUILTIN_CATALOGS_DIR  # Alias mantido para compatibilidade

_CUSTOM_CATALOGS_DIR: Optional[Path] = None
_LOCK = threading.RLock()

_CLASS_TRIB_DATA: Dict[str, Any] = {"csts": [], "classificacoes": []}
_CLASS_TRIB_BY_CODE: Dict[str, Dict[str, Any]] = {}
_CST_BY_CODE: Dict[str, Dict[str, Any]] = {}
_SERVICOS_CTRIBNAC: List[Dict[str, Any]] = []
_SERVICO_BY_CODE: Dict[str, Dict[str, Any]] = {}
_CORRELACOES_ANEXO_VIII: List[Dict[str, Any]] = []
_INDOP_TABELA: List[Dict[str, Any]] = []
_INDOP_BY_CODE: Dict[str, Dict[str, Any]] = {}
_NBS_TABELA: List[Dict[str, Any]] = []
_NBS_BY_CODE: Dict[str, Dict[str, Any]] = {}
_CATALOG_METADATA: Dict[str, Any] = {}


def get_catalogs_dir() -> Path:
    """Retorna o diretório ativo de leitura/armazenamento de catálogos (externo ou embutido)."""
    if _CUSTOM_CATALOGS_DIR is not None:
        return _CUSTOM_CATALOGS_DIR
    env_dir = (os.getenv("PYNFSE_CATALOGS_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return BUILTIN_CATALOGS_DIR


def _resolve_catalog_file(filename: str) -> Path:
    active_dir = get_catalogs_dir()
    candidate = active_dir / filename
    if candidate.exists() and candidate.is_file():
        return candidate
    return BUILTIN_CATALOGS_DIR / filename


def set_catalogs_dir(path: Optional[Union[str, Path]], reload: bool = True) -> Path:
    """Define um diretório externo gravável para sobreposição/atualização dos catálogos."""
    global _CUSTOM_CATALOGS_DIR
    with _LOCK:
        _CUSTOM_CATALOGS_DIR = Path(path).expanduser() if path else None
    if reload:
        reload_catalogs()
    return get_catalogs_dir()


def _build_nbs_index_from_correlacoes(correlacoes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Constrói índice NBS de fallback quando `nbs_tabela.json` não estiver presente."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for corr in correlacoes:
        cnbs = "".join(ch for ch in str(corr.get("cNBS") or "") if ch.isdigit()).zfill(9)
        if not cnbs or cnbs == "000000000":
            continue
        entry = grouped.setdefault(
            cnbs,
            {
                "cNBS": cnbs,
                "nbs": corr.get("nbs") or f"{cnbs[0]}.{cnbs[1:5]}.{cnbs[5:7]}.{cnbs[7:9]}",
                "descricao": corr.get("descricao_nbs") or "",
                "itens_lc116": [],
                "codigos_cTribNac": [],
                "no_anexo_viii": True,
                "fonte": corr.get("fonte") or "anexo_viii",
                "combinacoes": [],
            },
        )
        item_lc = corr.get("item_lc116")
        if item_lc and item_lc not in entry["itens_lc116"]:
            entry["itens_lc116"].append(item_lc)
        for ctrib in corr.get("codigos_cTribNac") or ([corr.get("cTribNac")] if corr.get("cTribNac") else []):
            if ctrib and ctrib not in entry["codigos_cTribNac"]:
                entry["codigos_cTribNac"].append(ctrib)
        ct = str(corr.get("cClassTrib") or "").strip().zfill(6)
        indop = str(corr.get("indop") or "").strip().zfill(6)
        cst = str(corr.get("cst") or ct[:3]).strip().zfill(3) if ct else ""
        combo = {"cClassTrib": ct, "cIndOp": indop, "cst": cst, "fonte": corr.get("fonte") or "anexo_viii"}
        if ct and indop and combo not in entry["combinacoes"]:
            entry["combinacoes"].append(combo)
    return sorted(grouped.values(), key=lambda x: x["cNBS"])


def reload_catalogs() -> Dict[str, Any]:
    """Recarrega todos os catálogos JSON do diretório ativo (externo + fallback embutido)."""
    global _CLASS_TRIB_DATA, _CLASS_TRIB_BY_CODE, _CST_BY_CODE
    global _SERVICOS_CTRIBNAC, _SERVICO_BY_CODE
    global _CORRELACOES_ANEXO_VIII, _INDOP_TABELA, _INDOP_BY_CODE
    global _NBS_TABELA, _NBS_BY_CODE, _CATALOG_METADATA

    with _LOCK:
        class_trib_path = _resolve_catalog_file("class_trib_completa.json")
        if class_trib_path.exists():
            _CLASS_TRIB_DATA = json.loads(class_trib_path.read_text(encoding="utf-8"))
            _CLASS_TRIB_BY_CODE = {item["codigo"]: item for item in _CLASS_TRIB_DATA.get("classificacoes", [])}
            _CST_BY_CODE = {item["cst"]: item for item in _CLASS_TRIB_DATA.get("csts", [])}

        servicos_path = _resolve_catalog_file("servicos_ctribnac.json")
        if servicos_path.exists():
            _SERVICOS_CTRIBNAC = json.loads(servicos_path.read_text(encoding="utf-8"))
            _SERVICO_BY_CODE = {item["cTribNac"]: item for item in _SERVICOS_CTRIBNAC}

        correlacoes_path = _resolve_catalog_file("correlacao_anexo_viii.json")
        if correlacoes_path.exists():
            _CORRELACOES_ANEXO_VIII = json.loads(correlacoes_path.read_text(encoding="utf-8"))

        indop_path = _resolve_catalog_file("indop_tabela.json")
        if indop_path.exists():
            _INDOP_TABELA = json.loads(indop_path.read_text(encoding="utf-8"))
            _INDOP_BY_CODE = {str(item["cIndOp"]).zfill(6): item for item in _INDOP_TABELA}

        nbs_path = _resolve_catalog_file("nbs_tabela.json")
        if nbs_path.exists():
            _NBS_TABELA = json.loads(nbs_path.read_text(encoding="utf-8"))
        else:
            _NBS_TABELA = _build_nbs_index_from_correlacoes(_CORRELACOES_ANEXO_VIII)
        _NBS_BY_CODE = {str(item["cNBS"]).zfill(9): item for item in _NBS_TABELA}

        meta_path = _resolve_catalog_file("catalog_metadata.json")
        if meta_path.exists():
            _CATALOG_METADATA = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            _CATALOG_METADATA = {}

        return obter_metadados_catalogos()


def _load_catalogs() -> None:
    """Alias interno mantido para compatibilidade."""
    reload_catalogs()


def obter_metadados_catalogos() -> Dict[str, Any]:
    """Retorna metadados de versão e contagens atuais dos catálogos em memória."""
    active_dir = get_catalogs_dir()
    return {
        "versao_db": _CATALOG_METADATA.get("versao_db") or "embutida",
        "data_versao_db": _CATALOG_METADATA.get("data_versao_db"),
        "descricao_versao_db": _CATALOG_METADATA.get("descricao_versao_db"),
        "anexo_viii_versao": _CATALOG_METADATA.get("anexo_viii_versao"),
        "anexo_vii_versao": _CATALOG_METADATA.get("anexo_vii_versao"),
        "anexo_viii_url": _CATALOG_METADATA.get("anexo_viii_url"),
        "anexo_vii_url": _CATALOG_METADATA.get("anexo_vii_url"),
        "atualizado_em": _CATALOG_METADATA.get("atualizado_em"),
        "fontes": _CATALOG_METADATA.get("fontes")
        or ["Portal Nacional NFS-e (gov.br/nfse)", "Calculadora Oficial IBS/CBS (Receita Federal)"],
        "catalogs_dir": str(active_dir),
        "usando_override_externo": active_dir.resolve() != BUILTIN_CATALOGS_DIR.resolve(),
        "totais": {
            "csts": len(_CLASS_TRIB_DATA.get("csts", [])),
            "cclasstrib": len(_CLASS_TRIB_DATA.get("classificacoes", [])),
            "servicos_ctribnac": len(_SERVICOS_CTRIBNAC),
            "nbs": len(_NBS_TABELA),
            "correlacoes": len(_CORRELACOES_ANEXO_VIII),
            "indop": len(_INDOP_TABELA),
        },
    }


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
    """Lista ou filtra os códigos cClassTrib da Reforma Tributária."""
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


def listar_nbs(
    q: Optional[str] = None,
    item_lc116: Optional[str] = None,
    apenas_anexo_viii: bool = False,
    limite: int = 1000,
) -> List[Dict[str, Any]]:
    """Lista ou pesquisa o catálogo completo de códigos NBS (920+ itens oficiais)."""
    termo = (q or "").strip().lower()
    termo_digits = "".join(ch for ch in termo if ch.isdigit())
    lc_norm = (item_lc116 or "").strip()

    resultados = []
    for item in _NBS_TABELA:
        if apenas_anexo_viii and not item.get("no_anexo_viii"):
            continue
        if lc_norm and lc_norm not in (item.get("itens_lc116") or []):
            continue
        if termo:
            texto = (
                f"{item.get('cNBS', '')} {item.get('nbs', '')} "
                f"{item.get('descricao', '')} {' '.join(item.get('itens_lc116') or [])}"
            ).lower()
            if termo not in texto and (not termo_digits or termo_digits not in (item.get("cNBS") or "")):
                continue
        resultados.append(item)
        if len(resultados) >= limite:
            break
    return resultados


def obter_nbs(c_nbs: str) -> Optional[Dict[str, Any]]:
    """Obtém os metadados completos e combinações válidas de um código NBS (9 dígitos)."""
    digits = "".join(ch for ch in (c_nbs or "") if ch.isdigit())
    if not digits:
        return None
    return _NBS_BY_CODE.get(digits.zfill(9))


def validar_combinacao_nbs(c_nbs: str, c_class_trib: str, c_ind_op: str) -> Dict[str, Any]:
    """Valida se a combinação `(cNBS, cClassTrib, cIndOp)` consta na base oficial (RFB / Anexo VIII)."""
    nbs_obj = obter_nbs(c_nbs)
    ct_norm = (c_class_trib or "").strip().zfill(6)
    indop_norm = "".join(ch for ch in (c_ind_op or "") if ch.isdigit()).zfill(6)

    if not nbs_obj:
        return {
            "valido": True,
            "status_calculadora": "desconhecido",
            "fonte": "nao_catalogado",
            "mensagem": f"NBS '{c_nbs}' não localizado na base local para conferência cruzada.",
            "combinacoes_recomendadas": [],
        }

    combos = nbs_obj.get("combinacoes") or []
    matches: List[Tuple[str, str]] = []
    for combo in combos:
        c_ct = str(combo.get("cClassTrib") or "").zfill(6)
        c_op = str(combo.get("cIndOp") or "").zfill(6)
        matches.append((c_ct, c_op))
        if c_ct == ct_norm and c_op == indop_norm:
            fonte = combo.get("fonte") or nbs_obj.get("fonte") or "anexo_viii"
            return {
                "valido": True,
                "status_calculadora": "aceita" if "calculadora" in fonte else fonte,
                "fonte": fonte,
                "mensagem": "Combinação compatível com a base oficial.",
                "combinacoes_recomendadas": combos,
            }

    if not combos and ct_norm == "000001":
        return {
            "valido": True,
            "status_calculadora": "regra_geral",
            "fonte": "regra_geral",
            "mensagem": "NBS sem vínculo específico no Anexo VIII; tributação integral (000001) aplicável como regra geral.",
            "combinacoes_recomendadas": combos,
        }

    return {
        "valido": False,
        "status_calculadora": "nao_prevista",
        "fonte": nbs_obj.get("fonte") or "oficial",
        "mensagem": (
            f"Combinação NBS={nbs_obj['cNBS']}, cClassTrib={ct_norm}, cIndOp={indop_norm} "
            "não consta entre as combinações mapeadas na base oficial."
        ),
        "combinacoes_recomendadas": combos[:10],
    }


def buscar_correlacoes_anexo_viii(
    q: Optional[str] = None,
    item_lc116: Optional[str] = None,
    c_trib_nac: Optional[str] = None,
    c_nbs: Optional[str] = None,
    c_class_trib: Optional[str] = None,
    indop: Optional[str] = None,
    limite: int = 100,
) -> List[Dict[str, Any]]:
    """Pesquisa nas correlações oficiais do Anexo VIII (LC 116 x NBS x INDOP x cClassTrib)."""
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
