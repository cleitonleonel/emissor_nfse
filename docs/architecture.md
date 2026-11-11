# Arquitetura do projeto

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Esta página explica como o pacote `pynfse` está organizado e como seus módulos interagem.

## Visão geral

O repositório é dividido em camadas claras:

- `pynfse/`: núcleo de automação do portal web, distribuição DFe, parser XML e geração offline de DANFS-e em PDF
- `pynfse/adn/`: motor completo da Sefin Nacional / ADN v1.01 (catálogos tributários, calculadora IBS/CBS, construtores XML, validador XSD, assinador XML-DSig e cliente mTLS assíncrono)
- `main.py`: script de entrada para consulta e download de notas
- `tests/`: suíte de testes automatizados (`pytest`)
- `docs/`: documentação técnica e enciclopédias de tags da NFS-e Nacional

## Fluxos principais

### 1. Fluxo de Consulta e Download (`ClienteNfseNacional`)

1. O `ClienteNfseNacional` autentica via Certificado A1 (`certificado.nfse.gov.br`) ou via Usuário/Senha no portal web.
2. Na listagem de notas (`listar_notas_emitidas` / `listar_notas_recebidas`):
   - **Com Certificado A1 (`usar_adn=True`)**: consome diretamente a API de distribuição do ADN (`/contribuintes/DFe/{nsu}`), descompacta os XMLs em GZip+Base64, filtra por período/tipo e salva os XMLs localmente.
   - **Sem Certificado (Portal Web)**: realiza o parsing das tabelas HTML de notas emitidas ou recebidas.
3. No download de PDF (`baixar_pdf`):
   - Tenta baixar via ADN (se houver certificado) ou via URL do portal.
   - Se o portal bloquear o download por Captcha/HTTP 403 e o XML correspondente já estiver salvo localmente, aciona o **`DanfseGenerator`** para gerar o PDF oficial offline.
   - Caso não haja XML local (modo apenas usuário/senha), faz fallback para a página de visualização/impressão (`obter_impressao_html`), salva como `.html` e dispara automaticamente o conversor **`html_to_xml`**, reconstruindo o XML padrão SPED e em seguida sintetizando a DANFS-e em PDF oficial via **`DanfseGenerator`**.

### 2. Fluxo de Emissão e Eventos via Sefin Nacional / ADN v1.01 (`pynfse.adn`)

1. **Catálogos e Tributação**: `catalog_service` fornece os metadados de `cTribNac`, `cNBS`, `cIndOp`, `CST` e `cClassTrib`, enquanto `calcular_tributacao` e `validar_regras_ibscbs` aplicam as fórmulas da NT 1.101 (ISSQN, retenções federais e IBS/CBS).
2. **Construção XML**: `build_dps_xml` (emissão/substituição) ou `build_evento_cancelamento_xml` / `build_evento_substituicao_xml` geram o XML no namespace oficial `http://www.sped.fazenda.gov.br/nfse` (definido em `pynfse.constants`).
3. **Assinatura Digital**: `DpsSigner` assina a tag alvo (`infDPS` ou `infPedReg`) usando XML-DSig Enveloped (`rsa-sha256`) com o certificado ICP-Brasil A1.
4. **Validação XSD Offline**: `XsdValidator` valida o XML assinado contra os schemas oficiais (`DPS_v1.01.xsd`, `pedRegEvento_v1.01.xsd`, `NFSe_v1.01.xsd`).
5. **Transmissão mTLS**: `AdnNfseClient` compacta o XML em GZip+Base64 e transmite via `httpx2` assíncrono com autenticação mTLS para a Sefin Nacional / ADN.

## Estrutura de diretórios atual

```text
emissor_nfse/
├── pynfse/
│   ├── adn/
│   │   ├── catalogs/          # Tabelas JSON (CST, cClassTrib, cTribNac, Anexo VIII, cIndOp)
│   │   ├── schemas_xsd/       # Schemas XSD oficiais v1.01
│   │   ├── adn_client.py      # Cliente mTLS assíncrono (httpx2)
│   │   ├── adn_signer.py      # Assinador XML-DSig (signxml + cryptography)
│   │   ├── catalog_service.py # Consultas em memória aos catálogos
│   │   ├── dps_builder.py     # Construtor XML DPS v1.01
│   │   ├── evento_builder.py  # Construtor XML de Eventos (e101101 / e105102)
│   │   ├── schemas.py         # Schemas Pydantic v2 (DPS, Prestador, Tomador, Servico...)
│   │   ├── tax_calculator.py  # Calculadora e validador tributário NT 1.101
│   │   └── xsd_validator.py   # Validador XSD com cache LXML
│   ├── assets/                # Logos da NFS-e e brasões municipais
│   ├── certificado.py         # Context manager PFX -> PEM temporário
│   ├── cliente_http.py        # Sessão requests com retry
│   ├── cliente_nfse.py        # Cliente de portal e distribuição ADN
│   ├── constants.py           # Namespaces oficiais, mapeamento UF, IBGE e domínio tributário
│   ├── danfse_generator.py    # Gerador offline de DANFS-e em PDF (fpdf2)
│   ├── html_to_xml.py         # Conversor de HTML de impressão para XML padrão SPED
│   ├── utils.py               # Utilitários compartilhados (datas, moedas, formatação, XML)
│   └── xml_parser.py          # Extrator de dados de XML da NFS-e
├── docs/                      # Documentação técnica, manuais e enciclopédias
│   ├── dicionario_360_tags_unicas_nfse.md / .pdf
│   ├── enciclopedia_completa_tags_nfse_nacional_645.md / .pdf
│   └── manual_nfse_nacional_2026_2027.pdf
├── src/                       # Logotipos oficiais NFS-e horizontal/vertical
├── scripts/                   # Geração de badge de cobertura
├── tests/                     # Suíte de testes automatizados (pytest)
│   ├── test_adn_module.py
│   ├── test_html_to_xml.py
│   └── ...
├── main.py                    # Exemplo de uso
├── pyproject.toml             # Configuração do pacote e ferramentas
├── README.md
└── requirements.txt
```
