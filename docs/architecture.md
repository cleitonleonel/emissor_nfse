# Arquitetura do projeto

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Esta página explica como o projeto está organizado e como o fluxo principal funciona hoje.

## Visão geral

O repositório está organizado em cinco áreas principais:

- `main.py`: ponto de entrada e exemplo de uso
- `core/`: cliente HTTP, certificado A1 e cliente NFS-e
- `utils/`: ferramentas auxiliares e testes manuais/legados
- `tests/`: suíte automatizada mantida
- `docs/`: documentação pública do projeto

## Fluxo principal

1. O `main.py` carrega variáveis de ambiente do `.env`.
2. O `ClienteNfseNacional` prepara a estrutura de download com base em `save_path` e `path_structure`.
3. O cliente autentica no portal usando usuário/senha ou certificado A1.
4. O cliente consulta notas emitidas no período informado.
5. Os arquivos XML e PDF são baixados em uma estrutura por cliente, tipo, ano, mês, status e extensão.

## Componentes do `core`

### `core.cliente_http`

Responsável pela camada HTTP comum.

- usa `requests.Session`
- aplica retry para instabilidades transitórias
- centraliza o envio de requisições

### `core.certificado`

Responsável pelo certificado digital A1.

- converte `.pfx` para PEM temporário
- remove os arquivos temporários ao final do uso

### `core.cliente_nfse`

Responsável pela integração com o portal do Emissor Nacional.

- autenticação
- listagem de notas emitidas e recebidas
- download de XML e PDF com organização por cliente
- envio de DPS com payload flexível

## Estrutura de diretórios atual

```text
emissor_nfse/
├── core/
├── docs/
├── downloads/
├── scripts/
├── tests/
├── utils/
├── certificados/
├── main.py
├── README.md
└── requirements.txt
```

## Observações

- O portal do governo pode mudar HTML e rotas sem aviso.
- Sempre valide autenticação e consultas após mudanças no portal.
- A suíte automatizada atualmente suportada fica em `tests/`; os arquivos em `utils/` são auxiliares e incluem testes legados.
- A documentação publicada em GitHub Pages usa os arquivos da pasta `docs/`.

