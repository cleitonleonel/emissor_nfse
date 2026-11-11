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

### Fallback Inteligente de PDF e Reconstrução de XML

Ao chamar `cliente.baixar_pdf(...)`:
1. Se o certificado A1 estiver configurado, tenta baixar o PDF oficial na API do ADN.
2. Caso contrário (ou se a requisição falhar), tenta baixar pelo portal web.
3. Se o portal bloquear o download com Captcha/403:
   - Se o arquivo `.xml` da nota já estiver salvo localmente, gera o PDF oficial offline através do **`DanfseGenerator`**.
   - Se não houver XML local (acesso via credenciais usuário/senha), obtém o HTML da página de impressão (`Visualizar/Impressao`), salva como `.html` e **automaticamente reconstrói o `.xml` oficial padrão SPED** via `converter_arquivo_html_para_xml`.
   - Em seguida, sintetiza imediatamente o `.pdf` da DANFS-e com brasão, QR Code e impostos calculados.

### 2. Conversão direta de HTML de Impressão para XML (`html_to_xml`)

Quando você já possui o HTML da visualização de impressão da NFS-e (ou fez scraping da tela de impressão):

```python
from pynfse import DanfseGenerator, converter_arquivo_html_para_xml, converter_html_para_xml

# Opção A: A partir do arquivo .html salvo
xml_gerado_path = converter_arquivo_html_para_xml("downloads/.../chave.html")
print(f"XML padrão SPED gerado em: {xml_gerado_path}")

# Opção B: A partir de string HTML em memória
xml_str = converter_html_para_xml("<html>...</html>")

# Gerando o DANFSe em PDF diretamente a partir do XML reconstruído
gerador = DanfseGenerator(xml_gerado_path)
gerador.gerar_pdf("saida_danfse.pdf")
```

## 3. Emitindo DPS v1.01 com Schemas Pydantic (`pynfse.adn`)

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

# 1. Configurar o prestador, tomador e serviço com Schemas Pydantic v2
prestador = Prestador(
    cnpj="19495981000113",
    inscricao_municipal="12345",
    razao_social="EMPRESA PRESTADORA LTDA",
    endereco=Endereco(
        logradouro="Av. Principal",
        numero="100",
        bairro="Centro",
        codigo_municipio=3201308,
        uf="ES",
        cep="29140000",
    ),
    regime_tributario="simples_nacional",
)

tomador = Tomador(
    documento="12345678000195",
    razao_social="CLIENTE EXEMPLO LTDA",
    endereco=Endereco(
        logradouro="Rua das Flores",
        numero="500",
        bairro="Jardim",
        codigo_municipio=3550308,
        uf="SP",
        cep="01310100",
    ),
)

servico = Servico(
    codigo_lc116="01.01.01",
    discriminacao="Desenvolvimento de sistema sob medida",
    valor_servicos=Decimal("1500.00"),
    cNBS="115021000",
    cClassTrib="000001",
    indop="030101",
)

# 2. Montar a DPS (calcula automaticamente ISSQN, Federais e IBS/CBS se `tributacao` não for passada)
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

# 3. Assinar digitalmente (XML-DSig ICP-Brasil A1) e validar contra o XSD v1.01
signer = DpsSigner(pfx_path="/caminho/para/certificado.pfx", pfx_password="senha")
xml_assinado = signer.sign_xml(dps)  # ou: dps.to_signed_xml(signer=signer)
assert XsdValidator.validar_dps(xml_assinado)["valido"] is True

# 4. Transmitir via mTLS para a Sefin Nacional / ADN
async def emitir():
    client = AdnNfseClient(
        cert_path="/caminho/para/certificado.pfx",
        cert_password="senha",
        ambiente="homologacao",
    )
    resposta = await client.emitir_dps(xml_assinado)  # também aceita `await client.emitir_dps(dps)`
    print(resposta)

asyncio.run(emitir())
```

## Testes e lint

```bash
pytest -q
ruff check .
```
