# pynfse — Documentação

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

![Coverage badge](assets/coverage.svg)

Esta documentação apresenta a biblioteca **`pynfse` (v0.2.0)**, projetada para automatizar o Emissor Nacional de NFS-e e integrar sistemas Python diretamente à API da **Sefin Nacional / ADN v1.01 (NT 1.101 — Reforma Tributária IBS/CBS)**.

## O que você encontra aqui

- **[Guia de uso](usage.md)**: instalação, configuração, consulta/download de notas, emissão via ADN v1.01 e geração offline de DANFS-e
- **[API](api.md)**: referência completa das classes e funções em `pynfse` e `pynfse.adn`
- **[Arquitetura](architecture.md)**: visão da estrutura modular do pacote e fluxos de execução
- **[Troubleshooting](troubleshooting.md)**: soluções para problemas comuns (Captcha/403, rate limit 429, validação XSD)
- **Referências normativas em `docs/`**:
  - [Dicionário de 360 Tags Únicas da NFS-e](dicionario_360_tags_unicas_nfse.md)
  - [Enciclopédia Completa de 645 Tags da NFS-e Nacional](enciclopedia_completa_tags_nfse_nacional_645.md)

## Estrutura resumida

- `main.py`: exemplo prático de execução do fluxo de consulta e download
- `pynfse/`: cliente HTTP, gerenciador de certificado A1, parser XML, gerador de DANFS-e em PDF (`fpdf2`) e cliente do portal/ADN
- `pynfse/adn/`: motor tributário IBS/CBS (NT 1.101), catálogos oficiais (CST, `cClassTrib`, `cTribNac`, Anexo VIII, `cIndOp`), builders de DPS/Eventos v1.01, validador XSD, assinador XML-DSig e cliente mTLS assíncrono (`httpx`)
- `tests/`: suíte de testes automatizados (`pytest`)
- `pyproject.toml`: configuração de empacotamento, dependências, `pytest` e `ruff`

## Destaques da versão 0.2.0

- Runtime alvo em **Python 3.12+**
- Suporte integral ao layout **v1.01 (NT 1.101 / LC 214/2025)** com grupos `<IBSCBS>`, validação XSD offline e assinatura ICP-Brasil A1
- Geração nativa de **DANFS-e em PDF** (`DanfseGenerator`) a partir do XML local, superando bloqueios de Captcha no portal
- Suíte automatizada com `pytest` e lint limpo com `ruff`
