# Troubleshooting

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Esta página reúne problemas comuns e como resolver.

## Não consigo autenticar

Verifique:

- se o usuário está sem pontuação (`CPF`/`CNPJ` apenas números)
- se a senha do portal está correta
- se o certificado A1 informado é válido
- se o arquivo `.pfx` e a senha do certificado realmente combinam

## Não achei notas emitidas

Confira:

- o intervalo de datas passado para `listar_notas_emitidas()`
- o formato das datas: `DD/MM/AAAA`
- se há documentos emitidos no período
- se a sessão foi autenticada com sucesso antes da consulta

## O download do XML/PDF falha

Verifique:

- se o link da nota ainda é válido
- se o diretório local tem permissão de escrita
- se o portal retornou erro antes de gerar o download

## GitHub Pages não está mostrando a documentação

Confirme no repositório:

- `Settings > Pages`
- origem configurada para `main` + `/docs`
- commit recente na branch principal contendo a pasta `docs/`

## O badge de coverage não atualiza

Verifique se o workflow de validação executou com sucesso e se o arquivo `docs/assets/coverage.svg` foi regenerado.

## O conteúdo da documentação ficou pouco claro

Sugestões:

- comece por `index.md`
- siga para `usage.md`
- consulte `api.md` para detalhes de métodos
- use `architecture.md` para entender o fluxo do projeto

## Observação final

Se o portal do Emissor Nacional mudar, alguns seletores HTML podem precisar ser revisados no `core/cliente_nfse.py`.

