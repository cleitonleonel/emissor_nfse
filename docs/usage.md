# Guia rápido — Como usar

Este documento mostra os passos mais comuns para utilizar o projeto.

## Instalação

Recomenda-se usar Poetry. Instale dependências (incluindo dev):

```bash
poetry install --with dev
```

Ou, se preferir `pip` (modo rápido):

```bash
pip install -r requirements.txt
```

## Configuração (variáveis de ambiente)

Crie um arquivo `.env` com as variáveis:

```env
NFSE_USUARIO=12345678000199
NFSE_SENHA=sua_senha_aqui
```

Se for usar certificado A1 (PFX), informe o caminho e senha ao instanciar o cliente:

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
    caminho_pfx="/caminho/para/certificado.pfx",
    senha_pfx="senha_do_certificado"
)

cliente.autenticar()
```

## Executando o exemplo principal

O `main.py` é um exemplo simples que carrega o `.env`, autentica e lista notas de um mês (configurado dentro do próprio arquivo).

```bash
python3 main.py
```

## Testes e lint

```bash
poetry run pytest
poetry run ruff check .
```

## Downloads

Os arquivos baixados (XML/PDF) são gravados em:

- `downloads/xmls`
- `downloads/pdfs`

Estes diretórios são criados automaticamente pelo cliente.

