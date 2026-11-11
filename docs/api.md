# API — Referência rápida do `pynfse`

> Navegação: [Início](index.md) · [Guia de uso](usage.md) · [API](api.md) · [Arquitetura](architecture.md) · [Troubleshooting](troubleshooting.md)

Este documento descreve as classes e funções principais exportadas por `pynfse` e pelo subpacote `pynfse.adn`.

---

## Módulo Principal (`pynfse`)

### `pynfse.cliente_nfse.ClienteNfseNacional`

Cliente síncrono para autenticação no portal, consulta e download de notas fiscais (via Portal Web ou ADN DFe).

- `autenticar(usar_certificado: bool = True) -> bool` — autentica via Certificado A1 (se configurado) ou via usuário/senha.
- `obter_cnpj() -> Optional[str]` — retorna o CNPJ/CPF detectado na sessão ou informado na inicialização.
- `listar_notas_emitidas(data_inicio: Optional[str] = None, data_fim: Optional[str] = None, usar_adn: bool = True) -> Dict[str, Any]` — lista notas emitidas no período (`DD/MM/AAAA`). Quando o certificado está configurado e `usar_adn=True`, consulta o lote DFe na API do ADN.
- `listar_notas_recebidas(data_inicio: Optional[str] = None, data_fim: Optional[str] = None, usar_adn: bool = True) -> Dict[str, Any]` — lista notas recebidas no período.
- `baixar_xml(url: str, status: str, data_emissao: Any = None) -> str` — baixa e salva o XML da nota na estrutura configurada (via ADN quando há certificado A1 ou via portal).
- `baixar_pdf(url: str, status: str, data_emissao: Any = None) -> str` — baixa o PDF da DANFS-e (via ADN ou portal). Caso o portal bloqueie por Captcha/403 ou retorne HTML de impressão, o cliente converte o HTML para XML padrão SPED via `html_to_xml` e sintetiza o PDF oficial offline através de `DanfseGenerator`.
- `obter_impressao_html(chave: str) -> Optional[str]` — recupera o HTML da página de impressão a partir da chave de acesso.
- `salvar_xml_adn(xml_bytes: bytes, chave: str, status: str = "gerada", data_emissao: Any = None) -> str` — normaliza e salva um XML proveniente do ADN.
- `usa_apenas_credenciais() -> bool` — indica se o cliente está operando exclusivamente via usuário/senha sem certificado digital ativo.

### `pynfse.html_to_xml` (Reconstrução XML a partir de HTML)

Reconstrutor de XML padrão SPED (`http://www.sped.fazenda.gov.br/nfse`) a partir do HTML de visualização de impressão (`Visualizar/Impressao`) do portal nacional. Permite recuperar os dados estruturados de NFS-e mesmo quando os downloads de XML/PDF oficiais estão bloqueados por Captcha.

- `converter_html_para_xml(html_content: str) -> str` — recebe a string com o código HTML da impressão da nota e retorna uma string formatada contendo o XML padrão SPED oficial (`<NFSe><infNFSe>...<DPS><infDPS>...`).
- `converter_arquivo_html_para_xml(caminho_html: Union[str, Path], caminho_xml_destino: Optional[Union[str, Path]] = None) -> str` — lê um arquivo `.html` de impressão e salva o `.xml` reconstruído no caminho especificado (ou ao lado do arquivo original). Retorna o caminho do arquivo gerado.

### `pynfse.danfse_generator.DanfseGenerator`

Gerador offline de DANFS-e em PDF utilizando `fpdf2` e `qrcode`.

- `DanfseGenerator(xml_path: str, logo_path: Optional[str] = None, status: Optional[str] = None)` — carrega o XML da NFS-e (aceita tanto o **caminho de um arquivo** quanto a **string direta com o XML**), identifica o município emitente e prepara o brasão/logotipo. Extrai resiliente os campos de competência (`dCompet`), base de cálculo (`vBC`), alíquota (`pAliqAplic`) e ISSQN (`vISSQN`).
- `gerar_pdf(output_path: str) -> str` — renderiza o PDF completo da DANFS-e (cabeçalho com QR Code, emitente, tomador, serviço, tributação municipal/federal, totais IBS/CBS da Reforma Tributária e marca d'água para notas canceladas/substituídas).

### `pynfse.constants` (Constantes e Mapeamentos)

Centraliza namespaces XML oficiais, códigos IBGE e tabelas de domínio tributário nacional:
- `NS_NFSE` (`http://www.sped.fazenda.gov.br/nfse`) e `NS_DSIG` (`http://www.w3.org/2000/09/xmldsig#`).
- `NS`: dicionário de namespaces para buscas XPath (`{"pynfse": NS_NFSE}`).
- `UF_ESTADOS`: mapeamento de siglas para nomes completos de todos os estados do Brasil.
- `MUNICIPIOS_IBGE`: códigos IBGE de 7 dígitos para tupla `(Nome Município, UF)`.
- `MUNICIPIOS_NOME_PARA_IBGE`: busca resiliente (com e sem acento) de `(Nome, UF)` para código IBGE.
- `OPCAO_SIMPLES_NACIONAL_MAP`, `REGIME_APURACAO_SN_MAP`, `TRIBUTACAO_ISSQN_MAP`, `TIPO_RETENCAO_ISSQN_MAP`: descrições e códigos do portal emissor.

### `pynfse.utils` (Funções Utilitárias e Formatadores)

Módulo central de funções utilitárias compartilhadas:
- `clean_digits(val: Any) -> str` — extrai apenas os dígitos numéricos de qualquer valor.
- `parse_datetime(val: Any) -> Optional[datetime]` — normaliza e converte formatos variados de datas (ISO 8601, pt-BR `DD/MM/AAAA [às] HH:MM:SS`, SQL) para `datetime`.
- `format_date(val: Any, include_time: bool = False) -> str` — formata data para o padrão brasileiro (`DD/MM/AAAA` ou `DD/MM/AAAA HH:MM:SS`).
- `format_currency(val: Any) -> str` / `parse_currency(val: Optional[str]) -> float` — converte e formata valores monetários brasileiros (`R$ 1.500,00` <-> `1500.00`).
- `format_percent(val: Any) -> str` — formata percentuais (`5,00%`).
- `format_cnpj_cpf(val: str) -> str` — formata dinamicamente CNPJ (14 dígitos) ou CPF (11 dígitos) com pontuação.
- `format_cep(val: str) -> str` — formata CEP (`XXXXX-XXX`).
- `format_phone(val: str) -> str` — formata telefones com DDD brasileiro.
- `extrair_codigo_inicial(val: Optional[str], default: str = "") -> str` — extrai o código numérico inicial de opções textuais (ex: `"1 - Operação Tributável"` -> `"1"`).
- `find_xml_text(root, xpath, default=None)` / `find_xml_float(root, xpath, default=0.0)` — busca elementos em árvores XML utilizando o namespace SPED padrão.
- `append_documento_xml(parent, documento)` — insere a tag filha `<CNPJ>` ou `<CPF>` no nó XML de acordo com o tamanho do documento.

### `pynfse.xml_parser.extrair_dados_nfse`

- `extrair_dados_nfse(xml_path: str) -> dict` — extrai `numero`, `chave`, `valor`, `valor_servico`, `data_emissao`, `cnpj_prestador`, `cnpj_tomador`, `cpf_tomador`, `nome_tomador`, `descricao_servico` e `status_code` usando apenas a biblioteca padrão (`xml.etree.ElementTree`).

### `pynfse.certificado.GerenciadorCertificadoA1`

- Context manager que converte um arquivo `.pfx` em um par temporário `(cert_pem_path, key_pem_path)` durante o bloco `with` e remove os arquivos temporários com segurança ao sair.

### `pynfse.cliente_http.ClienteHttp`

- Wrapper sobre `requests.Session` com política de retry para falhas transitórias (`500`, `502`, `503`, `504`).

---

## Subpacote Sefin Nacional / ADN v1.01 (`pynfse.adn`)

### `pynfse.adn.adn_client.AdnNfseClient`

Cliente assíncrono (`httpx2` + mTLS) para comunicação com a Sefin Nacional e o ADN nos ambientes de `homologacao` (Produção Restrita) e `producao`.

- `emitir_dps(xml_assinado: str, enviar_gzip_json: bool = True) -> Dict[str, Any]` — envia a DPS assinada (`POST /nfse`) e descompacta automaticamente o XML da NFS-e autorizada (`nfseXmlGZipB64`).
- `enviar_evento(xml_assinado: str, chave_nfse: Optional[str] = None, enviar_gzip_json: bool = True) -> Dict[str, Any]` — registra eventos de cancelamento (`e101101`) ou substituição (`e105102`).
- `consultar_nfse(chave_acesso: str) -> Dict[str, Any]` — consulta uma NFS-e pela chave de 50 dígitos.
- `consultar_dps(id_dps: str) -> Dict[str, Any]` — consulta uma DPS pelo identificador de 45 caracteres.
- `consultar_eventos(chave_acesso: str) -> Dict[str, Any]` — consulta os eventos vinculados a uma NFS-e.
- `listar_dfe_adn(cnpj: str, ultimo_nsu: int = 0) -> Dict[str, Any]` — consulta lotes de DFe por NSU no ADN (`GET /contribuintes/DFe/{nsu}`).
- `baixar_danfse(chave_acesso: str) -> Dict[str, Any]` — baixa os bytes do PDF oficial da DANFS-e no ADN.
- `consultar_parametros_municipais(cod_ibge: str) -> Dict[str, Any]` — consulta convênio e parâmetros do município pelo código IBGE de 7 dígitos.

### `pynfse.adn.schemas`, `pynfse.adn.dps_builder` & `pynfse.adn.evento_builder`

- **Schemas Pydantic v2 (`BaseModel`)**:
  - `DPS(prestador=..., tomador=..., servico=..., serie="900", numero=1, competencia=..., ambiente="homologacao")` — calcula a tributação automaticamente se `tributacao` não for informada e gera o XML via `dps.to_xml()`.
  - `Prestador(cnpj=..., inscricao_municipal=..., razao_social=..., endereco=Endereco(...), regime_tributario="simples_nacional", ...)`
  - `Tomador(documento=..., razao_social="Consumidor", endereco=Endereco(...), ...)`
  - `Endereco(logradouro=..., numero="S/N", bairro=..., codigo_municipio=..., uf=..., cep=...)`
  - `Servico(valor=..., cTribNac="010101", descricao=..., cNBS=..., cClassTrib="000001", indop="100301", ...)`
  - `Intermediario(documento=..., razao_social=...)`
  - `Substituicao(chSubstda=..., cMotivo="99", xMotivo=...)`
- `build_dps_xml_from_schema(dps: DPS) -> str` — constrói o XML `<DPS versao="1.01">` operando diretamente sobre os atributos validados do schema Pydantic `DPS` (sem conversão para `dict`).
- `build_dps_xml(prestador, tomador=None, servico=None, tributacao=None, ...) -> str` — aceita uma instância de `DPS` diretamente ou os schemas `Prestador`, `Tomador`, `Servico` (ou `dict` validados via `model_validate`).
- `formatar_id_dps(cod_municipio, documento_emitente, serie_dps, numero_dps) -> str` — gera o `Id` de 45 caracteres (`DPS` + 42 dígitos).
- `build_evento_cancelamento_xml(chave_nfse, documento_autor, motivo_codigo=1, motivo_descricao=..., ambiente=2) -> str` — gera o XML `<pedRegEvento versao="1.01">` para o evento `e101101`.
- `build_evento_substituicao_xml(chave_nfse_substituida, chave_nfse_substituta, documento_autor, ...) -> str` — gera o XML `<pedRegEvento versao="1.01">` para o evento `e105102`.

### `pynfse.adn.tax_calculator`

- `calcular_tributacao(valor_servicos: float, regime_prestador: str = "normal", cClassTrib: str = "000001", ...) -> Dict[str, Any]` — calcula ISSQN, retenções federais e o bloco completo da Reforma Tributária (`vBC` conforme regra E1530 para 2026, 2027–2032 e 2033+, reduções de alíquota por `cClassTrib`, diferimento, crédito presumido, tributação regular e compras governamentais).
- `validar_regras_ibscbs(c_class_trib: str, cst: Optional[str] = None, ...) -> Dict[str, Any]` — valida as regras de negócio do Anexo VI da NT 1.101 (E0958, E0959, E0964, E0965, E0971, E0972, E1522, E0905, E0910, E0931, E0966, E0967).

### `pynfse.adn.adn_signer.DpsSigner` & `pynfse.adn.xsd_validator.XsdValidator`

- `DpsSigner(pfx_data=None, pfx_password=None, pfx_path=None)`:
  - `sign_xml(xml_raw: str, tag_to_sign: str = "infDPS") -> str` — assina a tag indicada com XML-DSig Enveloped (`rsa-sha256`).
  - `gerar_pfx_autoassinado(...) -> bytes` — utilitário para geração de certificados `.pfx` de teste.
- `XsdValidator`:
  - `validar_dps(xml_content: str) -> Dict[str, Any]` — valida contra `DPS_v1.01.xsd`.
  - `validar_evento(xml_content: str) -> Dict[str, Any]` — valida contra `pedRegEvento_v1.01.xsd` ou `evento_v1.01.xsd`.
  - `validar_nfse(xml_content: str) -> Dict[str, Any]` — valida contra `NFSe_v1.01.xsd`.

### `pynfse.adn.catalog_service`

Funções de consulta aos catálogos oficiais em memória:
- `listar_cst(apenas_nfse=False)` / `obter_cst(cst)`
- `listar_cclasstrib(cst=None, apenas_nfse=False, apenas_anexo_viii=False, q=None)` / `obter_cclasstrib(codigo)`
- `listar_servicos_ctribnac(item_lc116=None, q=None, limite=400)` / `obter_servico_ctribnac(c_trib_nac)`
- `listar_subitens_lc116()`
- `buscar_correlacoes_anexo_viii(q=None, item_lc116=None, c_trib_nac=None, c_nbs=None, c_class_trib=None, indop=None, limite=100)`
- `listar_indop()` / `obter_indop(c_ind_op)`
- `listar_favoritos()`
