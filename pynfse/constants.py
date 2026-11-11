"""Constantes e tabelas de mapeamento do pynfse."""

from typing import Dict, Tuple

# Namespaces XML oficiais SPED / NFS-e Nacional
NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"
NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
NS = {"pynfse": NS_NFSE}

# Mapeamento de siglas das UFs para nomes completos dos estados brasileiros
UF_ESTADOS: Dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

# Códigos IBGE (7 dígitos) -> (Nome Município, UF)
# Base de referência para cidades com suporte mapeado
MUNICIPIOS_IBGE: Dict[str, Tuple[str, str]] = {
    "3201308": ("CARIACICA", "ES"),
    "3205002": ("SERRA", "ES"),
    "3205101": ("VIANA", "ES"),
    "3205200": ("VILA VELHA", "ES"),
    "3205309": ("VITÓRIA", "ES"),
    "3550308": ("SÃO PAULO", "SP"),
    "2112803": ("VIANA", "MA"),
}

# (Nome Município, UF) -> Código IBGE (7 dígitos)
# Suporta variações com ou sem acentuação para busca resiliente
MUNICIPIOS_NOME_PARA_IBGE: Dict[Tuple[str, str], str] = {
    ("CARIACICA", "ES"): "3201308",
    ("SERRA", "ES"): "3205002",
    ("VIANA", "ES"): "3205101",
    ("VILA VELHA", "ES"): "3205200",
    ("VITORIA", "ES"): "3205309",
    ("VITÓRIA", "ES"): "3205309",
    ("SAO PAULO", "SP"): "3550308",
    ("SÃO PAULO", "SP"): "3550308",
    ("VIANA", "MA"): "2112803",
}

# Descrições padronizadas para opções do Simples Nacional
OPCAO_SIMPLES_NACIONAL_MAP: Dict[str, str] = {
    "1": "Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)",
    "2": "Não Optante",
    "3": "Optante - Microempreendedor Individual (MEI)",
}

# Regime de Apuração dos Tributos pelo Simples Nacional
REGIME_APURACAO_SN_MAP: Dict[str, str] = {
    "1": "Regime de apuração dos tributos federais e municipal pelo Simples Nacional",
    "2": "Regime de estimativa / valor fixo",
}

# Tributação do ISSQN
TRIBUTACAO_ISSQN_MAP: Dict[str, str] = {
    "1": "Operação Tributável",
    "2": "Exportação de Serviço",
    "3": "Não Incidência",
    "4": "Imunidade",
}

# Tipo de Retenção do ISSQN
TIPO_RETENCAO_ISSQN_MAP: Dict[str, str] = {
    "1": "Não Retido",
    "2": "Retido pelo Tomador",
    "3": "Retido pelo Intermediário",
}
