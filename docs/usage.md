# Guia rápido — Como usar

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Este documento mostra os passos mais comuns para utilizar o projeto.

## Instalação

Crie um ambiente virtual e escolha uma das formas de instalação abaixo.

### Via `requirements.txt`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Via `pyproject.toml`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
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

O `main.py` carrega o `.env`, autentica e consulta notas de um período definido no próprio arquivo.

```bash
python main.py
```

## Testes e lint

```bash
pytest -q
ruff check .
```

> Se preferir, você também pode executar explicitamente `pytest -q tests`.

## Downloads

Os arquivos baixados (XML/PDF) seguem a estrutura configurada no cliente:

- diretório base (`save_path`)
- cliente/empresa (`{CLIENTE}` ou `{CNPJ}`)
- tipo de consulta (`{TIPO}`)
- ano, mês e status (`{ANO}`, `{MES}`, `{STATUS}`)
- pasta por extensão (`{EXT}`)

Por padrão, isso gera uma organização equivalente a `downloads/<cliente>/<tipo>/<ano>/<mes>/<status>/<ext>/`.

