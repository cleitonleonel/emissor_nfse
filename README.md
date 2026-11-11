# _pynfse — Emissor Nacional de NFS-e & API ADN (v1.01)_

<p align="center">
  <a href="https://github.com/cleitonleonel/emissor_nfse">
    <img src="https://github.com/cleitonleonel/emissor_nfse/blob/master/src/logo_nfse.png?raw=true" alt="pynfse logo" width="45%" height="auto">
  </a>
</p>

<p align="center">
  <i>Biblioteca e cliente Python para automação do Emissor Nacional de NFS-e e integração completa com a Sefin Nacional / ADN v1.01 (NT 1.101 — Reforma Tributária IBS/CBS).</i>
</p>

<p align="center">
<a href="https://github.com/cleitonleonel/emissor_nfse">
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-green" alt="Supported Python Versions"/>
  <img src="https://github.com/cleitonleonel/emissor_nfse/actions/workflows/ci.yml/badge.svg" alt="CI Status"/>
  <img src="https://raw.githubusercontent.com/cleitonleonel/emissor_nfse/refs/heads/master/docs/assets/coverage.svg" alt="Test Coverage"/>
</a>
</p>

## O que o projeto faz

- **Autenticação híbrida**: login no portal web com **usuário/senha** ou com **certificado digital A1** (`.pfx`) via mTLS.
- **Integração Sefin Nacional / ADN v1.01 (`pynfse.adn`)**:
  - **Emissão e Substituição de NFS-e**: construção do XML `<DPS versao="1.01">` (`build_dps_xml`) e submissão via mTLS (`AdnNfseClient`).
  - **Eventos Oficiais (`pedRegEvento` v1.01)**: cancelamento (`e101101`) e cancelamento por substituição (`e105102`).
  - **Motor Tributário da Reforma Tributária (NT 1.101 / LC 214/2025)**: cálculo e validação de ISSQN, retenções federais (PIS, COFINS, IRRF, CSLL, INSS) e novos tributos **IBS/CBS** (`calcular_tributacao`, `validar_regras_ibscbs`), incluindo regras de transição 2026 vs. 2027+, diferimento, crédito presumido, tributação regular e compras governamentais.
  - **Catálogos Tributários Embarcados**: consulta rápida em memória a 18 CSTs, 138 `cClassTrib`, 338 serviços `cTribNac` (LC 116/2003), 1.739 correlações do Anexo VIII (`LC 116 x NBS x cIndOp x cClassTrib`) e 28 indicadores `cIndOp`.
  - **Validação XSD v1.01 e Assinatura XML-DSig**: validação offline com schemas XSD oficiais (`XsdValidator`) e assinatura digital `rsa-sha256` Enveloped (`DpsSigner`).
- **Consulta e Download de Notas (`ClienteNfseNacional`)**:
  - Consulta de **notas emitidas** e **notas recebidas** via portal web ou diretamente pela API de distribuição DFe do ADN por NSU.
  - Download de **XML** e **PDF/DANFS-e** organizados dinamicamente por cliente, tipo, ano, mês, status e extensão.
  - **Fallback inteligente**: se o download do PDF for bloqueado por Captcha, recupera a impressão em HTML, reconstrói o XML padrão SPED e sintetiza a DANFS-e em PDF automaticamente.
- **Reconstrução de XML a partir de HTML (`html_to_xml`)**:
  - Reconstrói a estrutura XML oficial `<NFSe>` e `<DPS>` no namespace SPED a partir do HTML de impressão (`Visualizar/Impressao`), recuperando todos os campos de prestador, tomador, endereço, NBS, código de tributação nacional e impostos.
- **Geração Offline de DANFS-e em PDF (`DanfseGenerator`)**:
  - Gera o PDF da DANFS-e fiel ao layout oficial (com QR Code, brasão municipal e marca d'água para notas canceladas/substituídas) aceitando tanto **caminho de arquivo XML** quanto **string XML direta**.
  - Extração resiliente de campos (competência da DPS, alíquotas e base de cálculo).
- **Módulo Central de Constantes (`constants.py`)**:
  - Centraliza namespaces XML (`NS_NFSE`, `NS_DSIG`), tabelas de conversão de UFs, mapa bidirecional e tolerante a acentos para códigos de municípios do IBGE e tabelas de domínio tributário.

## Estrutura atual do repositório

- `main.py`: script de exemplo para autenticar, consultar e baixar notas
- `pynfse/`: pacote principal da biblioteca
  - `pynfse/adn/`: subpacote Sefin Nacional / ADN v1.01 (catálogos, motor IBS/CBS, construtores XML, validador XSD, assinador XML-DSig e cliente mTLS assíncrono `httpx2`)
  - `pynfse/assets/`: logotipos e brasões utilizados na geração da DANFS-e
  - `pynfse/constants.py`: namespaces e tabelas de domínio (UFs, IBGE, opções tributárias)
  - `pynfse/html_to_xml.py`: conversor de HTML de impressão da NFS-e para XML padrão SPED
  - `pynfse/utils.py`: utilitários compartilhados (datas, moedas, limpeza e formatação de documentos, XML)
- `tests/`: suíte de testes automatizados (`pytest`)
- `docs/`: documentação técnica, guia de API, manuais oficiais e enciclopédias de tags da NFS-e Nacional
- `scripts/`: scripts auxiliares (geração de badge de cobertura)
- `pyproject.toml`: metadados do pacote `pynfse` v0.2.0, dependências e configuração do `pytest` e `ruff`

## Requisitos

- Python 3.12+
- `pip` ou `poetry`
- Acesso ao portal do Emissor Nacional e/ou Certificado Digital ICP-Brasil A1 (`.pfx`)

## Instalação

### Com `pyproject.toml` (recomendado)

```bash
git clone https://github.com/cleitonleonel/emissor_nfse.git
cd emissor_nfse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Com `requirements.txt`

```bash
git clone https://github.com/cleitonleonel/emissor_nfse.git
cd emissor_nfse
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração

Crie um arquivo `.env` na raiz do projeto com as credenciais e/ou certificado:

```env
NFSE_USUARIO=12345678000199
NFSE_SENHA=sua_senha_aqui
CERTIFICADO_PATH=/caminho/para/certificado.pfx
CERTIFICADO_SENHA=senha_do_certificado
```

## Exemplos rápidos de uso

### 1. Consulta e download de notas (`ClienteNfseNacional`)

```python
from pynfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
    usuario="12345678000199",
    senha="sua_senha",
    caminho_pfx="/caminho/para/certificado.pfx",
    senha_pfx="senha_do_certificado",
)

cliente.autenticar()
resultado = cliente.listar_notas_emitidas("01/09/2025", "30/09/2025")

for nota in resultado.get("notas", []):
    situacao = nota.get("status_danfs-e", "gerada")
    data_emissao = nota.get("data_emissao")
    if nota.get("download_xml"):
        cliente.baixar_xml(nota["download_xml"], situacao, data_emissao)
    if nota.get("download_danfs-e"):
        cliente.baixar_pdf(nota["download_danfs-e"], situacao, data_emissao)
```

### 2. Emissão de DPS v1.01 com Schemas Pydantic (`pynfse.adn`)

```python
import asyncio
from datetime import datetime
from decimal import Decimal
from pynfse import (
    DPS,
    AdnNfseClient,
    DpsSigner,
    Endereco,
    Prestador,
    Servico,
    Tomador,
    XsdValidator,
)

# 1. Configurar o endereço e o prestador (schemas Pydantic v2)
prestador = Prestador(
    cnpj="19495981000113",
    inscricao_municipal="12345",
    razao_social="Empresa Exemplo LTDA",
    endereco=Endereco(
        logradouro="Rua Exemplo",
        numero="100",
        bairro="Centro",
        codigo_municipio=3201308,
        uf="ES",
        cep="29140000",
    ),
    email="contato@empresa.com",
    telefone="27999999999",
    regime_tributario="simples_nacional",
)

# 2. Configurar o cliente (Tomador) e o Serviço
tomador = Tomador(
    cnpj="12345678000195",
    razao_social="Cliente Tomador LTDA",
    endereco=Endereco(
        logradouro="Av. Brasil",
        numero="500",
        bairro="Jardins",
        codigo_municipio=3550308,
        uf="SP",
        cep="01430001",
    ),
)

servico = Servico(
    codigo_lc116="01.01.01",
    discriminacao="Desenvolvimento de software customizado",
    valor_servicos=Decimal("1000.00"),
    cNBS="115021000",
    cClassTrib="000001",
    indop="030101",
    iss_retido=False,
)

# 3. Montar a DPS (calcula automaticamente ISSQN, Retenções e IBS/CBS se `tributacao` for omitida)
dps = DPS(
    serie="900",
    numero=1,
    competencia="2026-11",
    data_emissao=datetime.now(),
    prestador=prestador,
    tomador=tomador,
    servico=servico,
    ambiente="homologacao",
)

# 4. Assinar digitalmente (XML-DSig ICP-Brasil A1) e validar contra o XSD oficial v1.01
signer = DpsSigner(pfx_path="/caminho/para/certificado.pfx", pfx_password="senha")
xml_assinado = signer.sign_xml(dps)  # ou: dps.to_signed_xml(signer=signer)

assert XsdValidator.validar_dps(xml_assinado)["valido"] is True

# 5. Enviar o XML assinado (ou o próprio objeto `dps`) via mTLS para a Sefin Nacional / ADN
async def enviar():
    client = AdnNfseClient(
        cert_path="/caminho/para/certificado.pfx",
        cert_password="senha",
        ambiente="homologacao",
    )
    resposta = await client.emitir_dps(xml_assinado)  # também aceita `await client.emitir_dps(dps)`
    print(resposta)

# asyncio.run(enviar())
```

### 3. Geração de DANFS-e em PDF a partir do XML (`DanfseGenerator`)

```python
from pynfse import DanfseGenerator

# Aceita caminho de arquivo ou string XML direta
gerador = DanfseGenerator("caminho/para/nota.xml", status="NORMAL")
gerador.gerar_pdf("caminho/para/danfse.pdf")
```

### 4. Conversão de HTML de Impressão para XML SPED (`html_to_xml`)

```python
from pynfse import converter_arquivo_html_para_xml, DanfseGenerator

# Converte o HTML de impressão baixado para XML SPED oficial
caminho_xml = converter_arquivo_html_para_xml("caminho/para/impressao.html")

# E gera o DANFSe em PDF imediatamente
DanfseGenerator(caminho_xml).gerar_pdf("caminho/para/danfse.pdf")
```

## Estrutura de downloads

Por padrão, os arquivos baixados pelo `ClienteNfseNacional` são organizados assim:

```text
downloads/
└── <cliente>/
    └── <tipo>/
        └── <ano>/
            └── <mes>/
                └── <status>/
                    └── <ext>/
                        └── <chave>.xml|pdf
```

## Testes e qualidade

O projeto usa `pytest` para testes automatizados e `ruff` para checagem e formatação:

```bash
pytest -q
ruff check .
```

## Documentação

A documentação detalhada fica em `docs/`:

- [Página inicial](docs/index.md)
- [Guia de uso](docs/usage.md)
- [Referência da API](docs/api.md)
- [Arquitetura](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Dicionário de 360 Tags Únicas da NFS-e](docs/dicionario_360_tags_unicas_nfse.md) (com versão PDF)
- [Enciclopédia Completa de 645 Tags da NFS-e Nacional](docs/enciclopedia_completa_tags_nfse_nacional_645.md) (com versão PDF)
- Manual Oficial da NFS-e Nacional (`docs/manual_nfse_nacional_2026_2027.pdf`)
- [Troubleshooting](docs/troubleshooting.md)
- [Dicionário de 360 Tags Únicas da NFS-e](docs/dicionario_360_tags_unicas_nfse.md)
- [Enciclopédia Completa de 645 Tags da NFS-e Nacional](docs/enciclopedia_completa_tags_nfse_nacional_645.md)

## Autor

**Cleiton Leonel Creton**

- Email: [cleiton.leonel@gmail.com](mailto:cleiton.leonel@gmail.com)
- GitHub: [@cleitonleonel](https://github.com/cleitonleonel)

---

**Última atualização:** Novembro de 2026
