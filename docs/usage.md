# Guia rápido — Como usar

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Este documento mostra os passos mais comuns para instalar e utilizar o `pynfse`.

## Instalação

Crie um ambiente virtual (Python 3.12+) e instale o projeto:

### Via `pyproject.toml` (recomendado)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Via `requirements.txt`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração (`.env`)

Crie um arquivo `.env` na raiz do projeto:

```env
NFSE_USUARIO=12345678000199
NFSE_SENHA=sua_senha_aqui
CERTIFICADO_PATH=/caminho/para/certificado.pfx
CERTIFICADO_SENHA=senha_do_certificado
```

## 1. Consultando e baixando notas (`ClienteNfseNacional`)

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

### Fallback Inteligente de PDF

Ao chamar `cliente.baixar_pdf(...)`:
1. Se o certificado A1 estiver configurado, tenta baixar o PDF oficial na API do ADN.
2. Caso contrário (ou se falhar), tenta baixar pelo portal web.
3. Se o portal bloquear o download com Captcha/403:
   - Se o arquivo `.xml` da nota estiver salvo localmente, gera o PDF oficial offline através do **`DanfseGenerator`**.
   - Se não houver XML local (acesso apenas com usuário e senha), baixa o HTML da página de impressão e salva como `.html`.

## 2. Emitindo DPS v1.01 e Calculando IBS/CBS (`pynfse.adn`)

```python
import asyncio
from pynfse import (
    AdnNfseClient,
    DpsSigner,
    XsdValidator,
    build_dps_xml,
    calcular_tributacao,
)

# 1. Calcular tributação (ISSQN + Federais + Reforma Tributária IBS/CBS)
trib = calcular_tributacao(
    valor_servicos=1500.00,
    regime_prestador="simples",
    cClassTrib="000001",
    cIndOp="030101",
    cTribNac="010101",
    cNBS="115021000",
)

# 2. Construir XML da DPS v1.01
xml_dps = build_dps_xml(
    prestador={"cnpj": "19495981000113", "codigo_municipio": "3201308", "regime": "simples"},
    tomador={"documento": "12345678000195", "razao_social": "CLIENTE EXEMPLO LTDA"},
    servico={"cTribNac": "010101", "descricao": "Desenvolvimento de sistema sob medida", "valor": 1500.00},
    tributacao=trib,
    serie_dps="900",
    numero_dps=1,
    ambiente="homologacao",
)

# 3. Assinar e validar no XSD v1.01
signer = DpsSigner(pfx_path="/caminho/para/certificado.pfx", pfx_password="senha")
xml_assinado = signer.sign_xml(xml_dps, tag_to_sign="infDPS")
assert XsdValidator.validar_dps(xml_assinado)["valido"] is True

# 4. Transmitir via mTLS para a Sefin Nacional / ADN
async def emitir():
    client = AdnNfseClient(
        ambiente="homologacao",
        cert_pem=signer.get_pem_certificate(),
        key_pem=signer.get_pem_private_key(),
    )
    resposta = await client.emitir_dps(xml_assinado)
    print(resposta)

asyncio.run(emitir())
```

## Testes e lint

```bash
pytest -q
ruff check .
```
