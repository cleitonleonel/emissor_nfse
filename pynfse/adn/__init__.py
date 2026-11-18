"""Subpacote ADN / Sefin Nacional (v1.01) do pynfse.

Contém toda a regra de negócio, catálogos oficiais (CST, cClassTrib, cTribNac, LC 116,
Anexo VIII e cIndOp), calculadora tributária (ISSQN, Retenções Federais e IBS/CBS conforme NT 1.101),
construtores XML (DPS e Eventos e101101/e105102), validador XSD v1.01, assinador XML-DSig
e cliente mTLS para Sefin Nacional / ADN.
"""

from pynfse.adn.adn_client import AdnNfseClient
from pynfse.adn.adn_signer import DpsSigner
from pynfse.adn.catalog_service import (
    buscar_correlacoes_anexo_viii,
    get_catalogs_dir,
    listar_cclasstrib,
    listar_cst,
    listar_favoritos,
    listar_indop,
    listar_nbs,
    listar_servicos_ctribnac,
    listar_subitens_lc116,
    obter_cclasstrib,
    obter_cst,
    obter_indop,
    obter_metadados_catalogos,
    obter_nbs,
    obter_servico_ctribnac,
    reload_catalogs,
    set_catalogs_dir,
    validar_combinacao_nbs,
)
from pynfse.adn.catalog_updater import (
    atualizar_catalogos_oficiais,
    verificar_atualizacao_oficial,
)
from pynfse.adn.dps_builder import (
    build_dps_xml,
    build_dps_xml_from_schema,
    clean_digits,
    converter_xml_dps_layout_nt,
    formatar_id_dps,
)
from pynfse.adn.evento_builder import (
    build_evento_cancelamento_xml,
    build_evento_substituicao_xml,
)
from pynfse.adn.schemas import (
    DPS,
    Endereco,
    Intermediario,
    Prestador,
    Servico,
    Substituicao,
    Tomador,
)
from pynfse.adn.tax_calculator import calcular_tributacao, validar_regras_ibscbs
from pynfse.adn.xsd_validator import XsdValidator

__all__ = [
    "AdnNfseClient",
    "DpsSigner",
    "XsdValidator",
    "DPS",
    "Prestador",
    "Tomador",
    "Endereco",
    "Servico",
    "Intermediario",
    "Substituicao",
    "build_dps_xml",
    "build_dps_xml_from_schema",
    "converter_xml_dps_layout_nt",
    "clean_digits",
    "formatar_id_dps",
    "build_evento_cancelamento_xml",
    "build_evento_substituicao_xml",
    "calcular_tributacao",
    "validar_regras_ibscbs",
    "listar_cst",
    "obter_cst",
    "listar_cclasstrib",
    "obter_cclasstrib",
    "listar_servicos_ctribnac",
    "obter_servico_ctribnac",
    "listar_subitens_lc116",
    "buscar_correlacoes_anexo_viii",
    "listar_indop",
    "obter_indop",
    "listar_nbs",
    "obter_nbs",
    "validar_combinacao_nbs",
    "obter_metadados_catalogos",
    "set_catalogs_dir",
    "get_catalogs_dir",
    "reload_catalogs",
    "atualizar_catalogos_oficiais",
    "verificar_atualizacao_oficial",
    "listar_favoritos",
]
