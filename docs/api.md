# API — referência rápida do `core`

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Este documento descreve de forma sucinta as classes e funções mais importantes dentro da pasta `core/`.

## `core.cliente_http.ClienteHttp`

- Sessão HTTP baseada em `requests.Session` com retries configurados.
- Método principal: `enviar_requisicao(metodo: str, url: str, **kwargs) -> requests.Response`

## `core.certificado.GerenciadorCertificadoA1`

Context manager que converte um arquivo `.pfx` para dois arquivos PEM temporários (certificado e chave), retornando uma tupla `(caminho_cert_pem, caminho_key_pem)` no `__enter__` e removendo os arquivos no `__exit__`.

Uso típico: use `GerenciadorCertificadoA1` com o caminho do `.pfx` e a senha do certificado para obter dois arquivos PEM temporários durante o contexto de uso e passá-los ao cliente HTTP quando necessário.

## `core.cliente_nfse.ClienteNfseNacional`

Principais métodos:

- `autenticar()` — tenta autenticar via certificado A1 (se informado) ou via usuário/senha.
- `listar_notas_emitidas(data_inicio: str, data_fim: str) -> Dict[str, Any]` — retorna `{"notas": [...]} ou {"notas": [], "erro": "mensagem"}`.
- `baixar_xml(url: str, xml_path: str = "downloads/xmls") -> str` — baixa e salva XML.
- `baixar_pdf(url: str, pdf_path: str = "downloads/pdfs") -> str` — baixa e salva PDF.
- `emitir_nota_simples(payload_dados: Dict[str, Any])` — envia um DPS (payload livre) para emissão.

Notas:

- Os métodos usam `core.cliente_http.ClienteHttp` para as requisições.
- Os downloads são implementados de forma a consumir memória de forma eficiente (stream para binários).

---

Para detalhes de implementação, consulte os arquivos em `core/`.

