# API — referência rápida do `core`

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Este documento descreve de forma sucinta as classes e funções mais importantes dentro da pasta `core/`.

## `core.cliente_http.ClienteHttp`

- Sessão HTTP baseada em `requests.Session` com retries configurados.
- Método principal: `enviar_requisicao(metodo: str, url: str, **kwargs) -> requests.Response`
- Centraliza o envio de requisições usadas pelo cliente NFS-e.

## `core.certificado.GerenciadorCertificadoA1`

Context manager que converte um arquivo `.pfx` para dois arquivos PEM temporários (certificado e chave), retornando uma tupla `(caminho_cert_pem, caminho_key_pem)` no `__enter__` e removendo os arquivos no `__exit__`.

Uso típico: use `GerenciadorCertificadoA1` com o caminho do `.pfx` e a senha do certificado para obter dois arquivos PEM temporários durante o contexto de uso e passá-los ao cliente HTTP quando necessário.

## `core.cliente_nfse.ClienteNfseNacional`

Principais métodos:

- `autenticar() -> bool` — autentica via certificado A1 (se informado) ou via usuário/senha.
- `obter_cnpj() -> Optional[str]` — retorna o CNPJ/CPF detectado após a autenticação.
- `listar_notas_emitidas(data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> Dict[str, Any]` — retorna as notas emitidas ou uma estrutura com `erro`.
- `listar_notas_recebidas(data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> Dict[str, Any]` — consulta notas recebidas no mesmo formato geral.
- `baixar_xml(url: str, status: str, data_emissao: Any = None) -> str` — baixa e salva XML com organização por cliente e metadados.
- `baixar_pdf(url: str, status: str, data_emissao: Any = None) -> str` — baixa e salva PDF com organização por cliente e metadados.
- `emitir_nota_simples(payload_dados: Dict[str, Any]) -> None` — envia um DPS (payload livre) para emissão.

Notas:

- Os métodos usam `core.cliente_http.ClienteHttp` para as requisições.
- Os downloads são implementados de forma a consumir memória de forma eficiente (stream para binários) e criam a estrutura configurada em `save_path`/`path_structure`.
- O cliente força `/{STATUS}/{EXT}` na estrutura final quando essas tags não são informadas.
- O XML é normalizado antes de ser salvo para reduzir espaços extras entre elementos.

---

Para detalhes de implementação, consulte os arquivos em `core/`.

