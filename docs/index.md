# Emissor_NFSe — Documentação

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

![Coverage badge](assets/coverage.svg)

Esta documentação foi organizada para ajudar você a entender rapidamente o projeto, executar o cliente principal e localizar detalhes técnicos quando necessário.

## O que você encontra aqui

- **Guia de uso**: instalação, configuração e execução
- **API**: referência rápida das classes e métodos em `core/`
- **Arquitetura**: visão da estrutura interna atual do projeto
- **Troubleshooting**: problemas comuns e como resolver

## Caminho sugerido de leitura

1. Comece por [Guia de uso](usage.md)
2. Consulte [Arquitetura](architecture.md) para entender o fluxo
3. Veja [API](api.md) para detalhes de implementação
4. Use [Troubleshooting](troubleshooting.md) caso encontre erros

## Estrutura resumida

- `main.py`: exemplo de execução do fluxo principal
- `core/`: cliente HTTP, certificado A1 e integração com NFS-e
- `utils/`: utilitários e testes manuais/legados
- `tests/`: suíte automatizada mantida
- `docs/`: documentação publicada pelo GitHub Pages
- `scripts/`: scripts auxiliares
- `pyproject.toml`: configuração de empacotamento, `pytest` e `ruff`

## Status do projeto

- integração contínua ativa
- testes automatizados em `pytest`
- lint com `ruff`
- documentação servida diretamente da pasta `docs/`
- runtime alvo em `Python 3.11+`
- suporte à API do Ambiente de Distribuição Nacional (ADN) para download e listagem usando Certificado A1
- mecanismo de fallback automático de PDF para HTML de impressão em caso de falha de download (HTTP 403)


