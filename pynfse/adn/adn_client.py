"""Cliente mTLS para comunicação com a Sefin Nacional / ADN (Ambiente de Dados Nacional da NFS-e).

Suporta os endpoints de Homologação (Produção Restrita) e Produção para:
- Emissão de NFS-e a partir de DPS assinada (POST /nfse ou POST /dps)
- Registro de Eventos de Cancelamento (e101101) e Substituição (e105102)
- Consulta de NFS-e por chave de acesso (50 dígitos) e DPS por ID
- Consulta de parâmetros municipais (convênio e alíquotas por código IBGE)
"""

from __future__ import annotations

import base64
import gzip
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

import httpx2 as httpx

from pynfse.utils import clean_digits


class AdnNfseClient:
    """Cliente HTTPX mTLS para a API da Sefin Nacional / ADN."""

    URLS = {
        "homologacao": "https://sefin.producaorestrita.nfse.gov.br/sefinnacional",
        "producao": "https://sefin.nfse.gov.br/sefinnacional",
    }

    ADN_URLS = {
        "homologacao": "https://adn.producaorestrita.nfse.gov.br",
        "producao": "https://adn.nfse.gov.br",
    }

    def __init__(
        self,
        ambiente: str = "homologacao",
        cert_pem: Optional[bytes] = None,
        key_pem: Optional[bytes] = None,
        cert_path: Optional[str] = None,
        cert_password: Optional[str] = None,
        pfx_path: Optional[str] = None,
        pfx_password: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        amb_norm = (ambiente or "homologacao").strip().lower()
        if amb_norm in ("1", "producao", "produção"):
            self.ambiente = "producao"
        elif amb_norm in ("2", "homologacao", "homologação", "homolog"):
            self.ambiente = "homologacao"
        else:
            raise ValueError(f"Ambiente inválido: '{ambiente}'. Use 'homologacao' ou 'producao'.")

        self.base_url = self.URLS[self.ambiente]
        self.adn_url = self.ADN_URLS[self.ambiente]
        self._signer = None
        caminho_pfx = cert_path or pfx_path
        senha_pfx = cert_password if cert_password is not None else pfx_password
        if caminho_pfx and (cert_pem is None or key_pem is None):
            from pynfse.adn.adn_signer import DpsSigner

            self._signer = DpsSigner(pfx_path=caminho_pfx, pfx_password=senha_pfx)
            cert_pem = self._signer.get_pem_certificate()
            key_pem = self._signer.get_pem_private_key()

        self.cert_pem = cert_pem
        self.key_pem = key_pem
        self.timeout = timeout
        self._temp_cert_file: Optional[str] = None
        self._temp_key_file: Optional[str] = None

    @staticmethod
    def compactar_xml_gzip_b64(xml_str: str) -> str:
        """Compacta uma string XML em GZip e codifica em Base64 (padrão Sefin Nacional / ADN)."""
        gz_bytes = gzip.compress(xml_str.encode("utf-8"))
        return base64.b64encode(gz_bytes).decode("ascii")

    @staticmethod
    def descompactar_xml_gzip_b64(b64_str: str) -> str:
        """Descompacta um payload Base64+GZip retornado pelo ADN/Sefin Nacional."""
        raw_bytes = base64.b64decode(b64_str)
        return gzip.decompress(raw_bytes).decode("utf-8")

    def _setup_mtls(self) -> Optional[tuple[str, str]]:
        if self.cert_pem and self.key_pem:
            f_cert = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            f_cert.write(self.cert_pem)
            f_cert.flush()
            f_cert.close()

            f_key = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
            f_key.write(self.key_pem)
            f_key.flush()
            f_key.close()

            self._temp_cert_file = f_cert.name
            self._temp_key_file = f_key.name
            return (self._temp_cert_file, self._temp_key_file)
        return None

    def _cleanup_mtls(self) -> None:
        for f in (self._temp_cert_file, self._temp_key_file):
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        self._temp_cert_file = None
        self._temp_key_file = None

    @asynccontextmanager
    async def _client_session(self) -> AsyncIterator[httpx.AsyncClient]:
        """Gerenciador de contexto assíncrono para sessões HTTPX com mTLS temporário."""
        cert_files = self._setup_mtls()
        try:
            async with httpx.AsyncClient(cert=cert_files, timeout=self.timeout, verify=False) as client:
                yield client
        finally:
            self._cleanup_mtls()

    async def _get_json_ou_texto(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[int, Any]:
        """Executa requisição GET mTLS e retorna (status_code, json_ou_texto)."""
        hdrs = {"Accept": "application/json, application/xml"}
        if headers:
            hdrs.update(headers)
        async with self._client_session() as client:
            res = await client.get(url, params=params, headers=hdrs)
            is_json = "application/json" in res.headers.get("content-type", "")
            return res.status_code, (res.json() if is_json else res.text)

    async def consultar_parametros_municipais(self, cod_ibge: str) -> Dict[str, Any]:
        """Consulta convênio e alíquotas do município na API de Parâmetros Municipais do ADN."""
        c_mun = clean_digits(cod_ibge).zfill(7)
        url = f"{self.base_url}/parametros_municipais/{c_mun}/convenio"
        try:
            status_code, dados = await self._get_json_ou_texto(url, headers={"Accept": "application/json"})
            return {
                "sucesso": status_code == 200,
                "status_code": status_code,
                "municipio": c_mun,
                "dados": dados,
            }
        except Exception as exc:
            return {"sucesso": False, "status_code": 500, "municipio": c_mun, "erro": str(exc)}

    async def emitir_dps(self, dps_ou_xml: Any, enviar_gzip_json: bool = True) -> Dict[str, Any]:
        """Submete a DPS (instância do schema `DPS` ou XML assinado) à Sefin Nacional / ADN."""
        from pynfse.adn.schemas import DPS

        if isinstance(dps_ou_xml, DPS):
            xml_gerado = dps_ou_xml.to_xml()
            xml_assinado = (
                self._signer.sign_xml(xml_gerado, tag_to_sign="infDPS") if self._signer is not None else xml_gerado
            )
        else:
            xml_assinado = str(dps_ou_xml)

        url = f"{self.base_url}/nfse"
        dps_b64 = self.compactar_xml_gzip_b64(xml_assinado)

        try:
            async with self._client_session() as client:
                if enviar_gzip_json:
                    res = await client.post(
                        url,
                        json={"dpsXmlGZipB64": dps_b64},
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                    )
                else:
                    res = await client.post(
                        url,
                        content=xml_assinado.encode("utf-8"),
                        headers={
                            "Content-Type": "application/xml; charset=utf-8",
                            "Accept": "application/json, application/xml",
                        },
                    )

                is_json = "application/json" in res.headers.get("content-type", "")
                corpo = res.json() if is_json else res.text
                nfse_xml = None
                chave_acesso = None
                if isinstance(corpo, dict):
                    chave_acesso = corpo.get("chNFSe") or corpo.get("chaveAcesso")
                    b64_nfse = corpo.get("nfseXmlGZipB64") or corpo.get("arquivoXml")
                    if b64_nfse:
                        try:
                            nfse_xml = self.descompactar_xml_gzip_b64(b64_nfse)
                        except Exception:
                            pass

                return {
                    "sucesso": res.status_code in (200, 201),
                    "status_code": res.status_code,
                    "ambiente": self.ambiente,
                    "chave_acesso": chave_acesso,
                    "nfse_xml": nfse_xml,
                    "dps_xml_gzip_b64": dps_b64,
                    "mensagem": (
                        "DPS recebida e NFS-e autorizada com sucesso pelo ADN/Sefin Nacional."
                        if res.status_code in (200, 201)
                        else "Retorno do ambiente ADN/Sefin Nacional."
                    ),
                    "resposta": corpo,
                }
        except Exception as exc:
            return {
                "sucesso": False,
                "status_code": 500,
                "ambiente": self.ambiente,
                "dps_xml_gzip_b64": dps_b64,
                "mensagem": "Erro de conexão mTLS com a Sefin Nacional / ADN.",
                "erro": str(exc),
            }

    async def enviar_evento(
        self,
        xml_assinado: str,
        chave_nfse: Optional[str] = None,
        enviar_gzip_json: bool = True,
    ) -> Dict[str, Any]:
        """Envia pedido de registro de evento (cancelamento e101101 ou substituição e105102) ao ADN/Sefin Nacional."""
        chave_limpa = clean_digits(chave_nfse)
        url = (
            f"{self.base_url}/nfse/{chave_limpa}/eventos" if len(chave_limpa) == 50 else f"{self.base_url}/pedRegEvento"
        )
        evt_b64 = self.compactar_xml_gzip_b64(xml_assinado)

        try:
            async with self._client_session() as client:
                if enviar_gzip_json:
                    res = await client.post(
                        url,
                        json={"pedidoRegistroEventoXmlGZipB64": evt_b64},
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                    )
                else:
                    res = await client.post(
                        url,
                        content=xml_assinado.encode("utf-8"),
                        headers={
                            "Content-Type": "application/xml; charset=utf-8",
                            "Accept": "application/json, application/xml",
                        },
                    )

                is_json = "application/json" in res.headers.get("content-type", "")
                corpo = res.json() if is_json else res.text
                return {
                    "sucesso": res.status_code in (200, 201),
                    "status_code": res.status_code,
                    "ambiente": self.ambiente,
                    "evento_xml_gzip_b64": evt_b64,
                    "resposta": corpo,
                }
        except Exception as exc:
            return {
                "sucesso": False,
                "status_code": 500,
                "ambiente": self.ambiente,
                "evento_xml_gzip_b64": evt_b64,
                "erro": str(exc),
            }

    async def consultar_nfse(self, chave_acesso: str) -> Dict[str, Any]:
        """Consulta NFS-e pela chave de 50 dígitos no ADN/Sefin Nacional."""
        chave_limpa = clean_digits(chave_acesso)
        url = f"{self.base_url}/nfse/{chave_limpa}"
        try:
            status_code, conteudo = await self._get_json_ou_texto(url)
            return {
                "sucesso": status_code == 200,
                "status_code": status_code,
                "conteudo": conteudo,
            }
        except Exception as exc:
            return {"sucesso": False, "status_code": 500, "erro": str(exc)}

    async def consultar_dps(self, id_dps: str) -> Dict[str, Any]:
        """Consulta DPS pelo seu identificador (45 caracteres) na Sefin Nacional."""
        id_limpo = (id_dps or "").strip()
        url = f"{self.base_url}/dps/{id_limpo}"
        try:
            status_code, conteudo = await self._get_json_ou_texto(url)
            return {
                "sucesso": status_code == 200,
                "status_code": status_code,
                "id_dps": id_limpo,
                "conteudo": conteudo,
            }
        except Exception as exc:
            return {"sucesso": False, "status_code": 500, "id_dps": id_limpo, "erro": str(exc)}

    async def consultar_eventos(self, chave_acesso: str) -> Dict[str, Any]:
        """Consulta os eventos vinculados a uma NFS-e pela chave de 50 dígitos."""
        chave_limpa = clean_digits(chave_acesso)
        url = f"{self.base_url}/nfse/{chave_limpa}/eventos"
        try:
            status_code, eventos = await self._get_json_ou_texto(url)
            return {
                "sucesso": status_code == 200,
                "status_code": status_code,
                "chave_acesso": chave_limpa,
                "eventos": eventos,
            }
        except Exception as exc:
            return {"sucesso": False, "status_code": 500, "chave_acesso": chave_limpa, "erro": str(exc)}

    async def listar_dfe_adn(self, cnpj: str, ultimo_nsu: int = 0) -> Dict[str, Any]:
        """Consulta a distribuição de DF-e por NSU no ADN (/contribuintes/DFe/{nsu}?cnpj=...)."""
        cnpj_limpo = clean_digits(cnpj)
        nsu_str = str(max(0, int(ultimo_nsu))).zfill(20)
        url = f"{self.adn_url}/contribuintes/DFe/{nsu_str}"
        try:
            status_code, dados = await self._get_json_ou_texto(
                url, params={"cnpj": cnpj_limpo}, headers={"Accept": "application/json"}
            )
            return {
                "sucesso": status_code == 200,
                "status_code": status_code,
                "cnpj": cnpj_limpo,
                "nsu_consultado": nsu_str,
                "dados": dados,
            }
        except Exception as exc:
            return {
                "sucesso": False,
                "status_code": 500,
                "cnpj": cnpj_limpo,
                "nsu_consultado": nsu_str,
                "erro": str(exc),
            }

    async def baixar_danfse(self, chave_acesso: str) -> Dict[str, Any]:
        """Baixa o PDF do DANFSe diretamente da API do ADN (/danfse/{chave})."""
        chave_limpa = clean_digits(chave_acesso)
        url = f"{self.adn_url}/danfse/{chave_limpa}"
        try:
            async with self._client_session() as client:
                res = await client.get(url, headers={"Accept": "application/pdf, application/json"})
                is_pdf = res.status_code == 200 and (
                    "application/pdf" in res.headers.get("content-type", "").lower() or res.content.startswith(b"%PDF")
                )
                return {
                    "sucesso": is_pdf,
                    "status_code": res.status_code,
                    "chave_acesso": chave_limpa,
                    "pdf_bytes": res.content if is_pdf else None,
                    "content_type": res.headers.get("content-type", ""),
                    "mensagem": "PDF baixado com sucesso." if is_pdf else res.text,
                }
        except Exception as exc:
            return {
                "sucesso": False,
                "status_code": 500,
                "chave_acesso": chave_limpa,
                "pdf_bytes": None,
                "erro": str(exc),
            }
