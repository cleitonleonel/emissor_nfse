# _Emissor_NFSe_

[![CI](https://github.com/cleitonleonel/emissor_nfse/actions/workflows/ci.yml/badge.svg)](https://github.com/cleitonleonel/emissor_nfse/actions/workflows/ci.yml)
[![codecov](https://raw.githubusercontent.com/cleitonleonel/emissor_nfse/refs/heads/master/docs/assets/coverage.svg)](https://github.com/cleitonleonel/emissor_nfse)

<img src="https://github.com/cleitonleonel/emissor_nfse/blob/master/src/NFS-e.png?raw=true" alt="emissor_nfse" width="200"/>

Projeto em Python para automatizar parte do fluxo do Emissor Nacional de NFS-e.

Este repositório tem dois pontos principais de entrada:

- `main.py`: script de exemplo para autenticar e consultar notas emitidas.
- `core/`: módulos reutilizáveis para HTTP, certificado A1 e cliente NFS-e.

> Observação: este projeto conversa com páginas do portal do governo. Mudanças no HTML ou nas rotas podem exigir ajustes futuros.

## O que o projeto já faz

- Autenticação com usuário/senha.
- Autenticação com certificado digital A1 (`.pfx`).
- Consulta de notas emitidas em um intervalo de datas.
- Download de XML e PDF das notas encontradas.
- Gerenciamento de certificado temporário em PEM durante a autenticação.

## Requisitos

- Python 3.10+
- Dependências em `requirements.txt`

## Instalação

### Com Poetry

```bash
poetry install --with dev
```

### Com pip

```bash
git clone https://github.com/cleitonleonel/emissor_nfse.git
cd emissor_nfse
pip3 install -r requirements.txt
```

## Configuração rápida

O `main.py` lê as variáveis abaixo:

- `NFSE_USUARIO`: CPF/CNPJ sem pontuação
- `NFSE_SENHA`: senha do portal

Exemplo de arquivo `.env`:

```env
NFSE_USUARIO=12345678000199
NFSE_SENHA=sua_senha_aqui
```

Se você quiser usar autenticação com certificado A1 no seu próprio script, o cliente `core` também aceita:

- caminho do `.pfx`
- senha do certificado

## Execução do exemplo principal

```bash
python3 main.py
```

## Testes e lint

O projeto já vem preparado para usar `pytest` e `ruff` via Poetry.

```bash
poetry run pytest
poetry run ruff check .
```

Se quiser aplicar correções automáticas do Ruff:

```bash
poetry run ruff check . --fix
```

O fluxo do `main.py` é este:

Documentação do projeto (GitHub Pages)

A documentação está disponível na pasta `docs/` deste repositório e é publicada via GitHub Pages quando você fizer push para a branch `main`.

> Observação: para usar a pasta `docs/` como origem do site, habilite GitHub Pages em `Settings > Pages` e selecione a origem `main` + `/docs`.

- Página principal: `docs/index.md`
- Guia de uso: `docs/usage.md`
- Referência da API: `docs/api.md`
- Arquitetura: `docs/architecture.md`
- Troubleshooting: `docs/troubleshooting.md`

1. Carrega variáveis de ambiente.
2. Autentica no portal.
3. Consulta notas emitidas de até 30 dias a contar da data atual.
4. Baixa XML e PDF de cada nota encontrada, quando os links existem.

## Exemplos de uso com `core`

### 1) Autenticar com usuário e senha

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
	usuario="12345678000199",
	senha="minha_senha"
)

cliente.autenticar()
print("Autenticado com sucesso")
```

### 2) Autenticar com certificado A1

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
	caminho_pfx="/caminho/para/certificado.pfx",
	senha_pfx="senha_do_certificado"
)

cliente.autenticar()
print("Autenticado via certificado")
```

### 3) Listar notas emitidas em um período

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
	usuario="12345678000199",
	senha="minha_senha"
)
cliente.autenticar()

resultado = cliente.listar_notas_emitidas("01/01/2026", "31/01/2026")

if "erro" in resultado:
	print("Erro:", resultado["erro"])
else:
	for nota in resultado["notas"]:
		print(nota)
```

### 4) Baixar XML e PDF de uma nota

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
	usuario="12345678000199",
	senha="minha_senha"
)
cliente.autenticar()

resultado = cliente.listar_notas_emitidas("01/01/2026", "31/01/2026")

for nota in resultado.get("notas", []):
	if nota.get("download_xml"):
		caminho_xml = cliente.baixar_xml(nota["download_xml"])
		print("XML salvo em:", caminho_xml)

	if nota.get("download_danfs-e"):
		caminho_pdf = cliente.baixar_pdf(nota["download_danfs-e"])
		print("PDF salvo em:", caminho_pdf)
```

### 5) Enviar uma DPS com payload personalizado

###### Obs: Ainda em desenvolvimento - o endpoint e formato do payload podem mudar conforme testes avançam.


O método `emitir_nota_simples()` recebe um dicionário livre com os dados da requisição:

```python
from core.cliente_nfse import ClienteNfseNacional

cliente = ClienteNfseNacional(
	usuario="12345678000199",
	senha="minha_senha"
)
cliente.autenticar()

payload = {
	"campo_exemplo": "valor",
	"outro_campo": "valor_2",
}

cliente.emitir_nota_simples(payload)
```

## Casos de uso sugeridos

### Integração com ERP ou sistema interno

Use o cliente para autenticar, consultar notas emitidas e baixar XML/PDF para arquivamento automático.

### Rotina de conciliação fiscal

Busque notas por período e compare os registros baixados com o seu banco de dados ou planilha de controle.

### Backup documental

Faça download periódico de XML e DANFS-e/PDF para manter um histórico local de documentos fiscais.

### Automação de atendimento

Gere respostas rápidas para clientes ou equipe interna usando os dados consultados diretamente do portal.

## Estrutura principal do projeto

- `main.py`: exemplo de fluxo completo.
- `core/cliente_http.py`: camada HTTP com retry.
- `core/certificado.py`: conversão temporária de PFX para PEM.
- `core/cliente_nfse.py`: cliente principal para autenticação, consulta e download.

## Observações importantes

- As datas em `listar_notas_emitidas()` devem estar no formato `DD/MM/AAAA`.
- Os downloads são gravados em `downloads/xmls` e `downloads/pdfs` por padrão.
- O cliente usa `verify=False` em algumas chamadas para lidar com o portal; isso é comum em integrações desse tipo, mas deve ser avaliado no seu ambiente.
- O projeto depende da estrutura atual das páginas do portal; se o HTML mudar, os seletores podem precisar de atualização.

## Contribuição

Sugestões, correções e melhorias são bem-vindas.

## Este projeto ajudou você?

Se esse projeto lhe ajudar de alguma forma, sinta-se livre para me pagar um café, kkkk... Basta apontar a câmera do seu celular para um dos QR codes abaixo.

<img src="https://github.com/cleitonleonel/pypix/blob/master/qrcode.png?raw=true" alt="QRCode Doação" width="250"/>

<img src="https://github.com/cleitonleonel/pypix/blob/master/artistic.gif?raw=true" alt="QRCode Doação" width="250"/>

## Autor

Cleiton Leonel Creton ==> cleiton.leonel@gmail.com
