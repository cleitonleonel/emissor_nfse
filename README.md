# _Emissor_NFSe_

[![CI](https://github.com/cleitonleonel/emissor_nfse/actions/workflows/ci.yml/badge.svg)](https://github.com/cleitonleonel/emissor_nfse/actions/workflows/ci.yml)
[![coverage](https://raw.githubusercontent.com/cleitonleonel/emissor_nfse/refs/heads/main/docs/assets/coverage.svg)](https://github.com/cleitonleonel/emissor_nfse)

<img src="https://github.com/cleitonleonel/emissor_nfse/blob/main/src/NFS-e.png?raw=true" alt="emissor_nfse" width="200"/>

Cliente Python para automatizar o uso do **Emissor Nacional de NFS-e** (Notas Fiscais de Serviço Eletrônicas).

## O que o projeto faz

- autenticação no portal com **usuário/senha**
- autenticação com **certificado digital A1** (`.pfx`)
- consulta de **notas emitidas** e **notas recebidas**
- download de **XML** e **PDF/DANFS-e**
- organização dos arquivos por **cliente, tipo, ano, mês, status e extensão**
- conversão temporária e segura de PFX para PEM
- testes automatizados com `pytest` e lint com `ruff`

## Estrutura atual do repositório

- `main.py`: script de exemplo para autenticar, consultar e baixar notas
- `core/`: biblioteca principal reutilizável
- `tests/`: suíte automatizada mantida no fluxo atual
- `utils/`: utilitários e testes manuais/legados
- `docs/`: documentação publicada via GitHub Pages
- `scripts/`: scripts auxiliares
- `downloads/`: saída padrão dos arquivos baixados
- `certificados/`: certificados locais usados em testes/execução manual
- `pyproject.toml`: metadados do projeto, configuração do `pytest` e do `ruff`

> **Importante:** este repositório atual é centrado no pacote `core/` e no script `main.py`. As instruções abaixo refletem essa estrutura real.

## Requisitos

- Python 3.11+
- `pip`
- acesso ao portal do Emissor Nacional
- opcionalmente, um certificado A1 em `.pfx`

## Instalação

Você pode instalar pelas dependências fixadas em `requirements.txt` ou pelo `pyproject.toml`.

### Com `requirements.txt`

```bash
git clone https://github.com/cleitonleonel/emissor_nfse.git
cd emissor_nfse
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Com `pyproject.toml`

```bash
git clone https://github.com/cleitonleonel/emissor_nfse.git
cd emissor_nfse
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Configuração

Crie um arquivo `.env` na raiz do projeto com as credenciais do portal:

```env
NFSE_USUARIO=12345678000199
NFSE_SENHA=sua_senha_aqui
```

Se for usar certificado A1, informe o caminho e a senha ao instanciar o cliente:

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
    usuario="12345678000199",
    senha="sua_senha",
    caminho_pfx="/caminho/para/certificado.pfx",
    senha_pfx="senha_do_certificado",
)
```

## Execução do exemplo

O `main.py` autentica, consulta notas em um período fixo e baixa XML/PDF quando disponíveis.

```bash
python main.py
```

## Exemplos de uso do `core`

### Autenticar

Instancie `ClienteNfseNacional` com `usuario` e `senha` e chame `autenticar()`.

### Consultar notas emitidas

Depois de autenticar, use `cliente.listar_notas_emitidas("01/01/2026", "31/01/2026")` e verifique se a resposta contém a chave `erro`.

### Baixar XML e PDF

Itere sobre `resultado.get("notas", [])` e, quando houver links, chame `cliente.baixar_xml(...)` e `cliente.baixar_pdf(...)` com o `status_danfs-e` da nota.

## Estrutura de downloads

Por padrão, os arquivos são organizados assim:

```text
downloads/
└── <cliente>/
    └── <tipo>/
        └── <ano>/
            └── <mes>/
                └── <status>/
                    └── <ext>/
                        └── arquivo.xml|pdf
```

Se `path_structure` não informar `STATUS` ou `EXT`, o cliente os adiciona automaticamente.

## Testes e qualidade

O projeto usa `pytest` para testes e `ruff` para lint.

```bash
pytest -q
ruff check .
```

> Se você quiser executar apenas a suíte principal explicitamente, `pytest -q tests` também funciona.

## Documentação

A documentação detalhada fica em `docs/`:

- [Página inicial](docs/index.md)
- [Guia de uso](docs/usage.md)
- [API](docs/api.md)
- [Arquitetura](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)

## Observações importantes

- Datas devem estar no formato `DD/MM/AAAA`.
- O portal pode mudar HTML e rotas sem aviso.
- `verify=False` é usado em chamadas específicas por compatibilidade com o portal.
- Os certificados temporários gerados pelo contexto são removidos automaticamente ao final do uso.

## Contribuição

1. Faça um fork
2. Crie uma branch
3. Execute `pytest -q tests` e `ruff check .`
4. Envie um Pull Request

## Autor

**Cleiton Leonel Creton**

- Email: [cleiton.leonel@gmail.com](mailto:cleiton.leonel@gmail.com)
- GitHub: [@cleitonleonel](https://github.com/cleitonleonel)

---

**Última atualização:** Maio de 2026
