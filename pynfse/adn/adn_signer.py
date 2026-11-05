"""Módulo de Assinatura Digital W3C XML-DSig padrão ADN / Sefin Nacional NFS-e v1.01.

Utiliza certificado digital ICP-Brasil A1 PKCS#12 (.pfx/.p12) para assinar as tags:
- infDPS (Declaração de Prestação de Serviços)
- infPedReg (Pedido de Registro de Evento: cancelamento e101101 / substituição e105102)
- infEvento (Evento completo)
- infNFSe (Nota Fiscal de Serviço Eletrônica)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"


class DpsSigner:
    """Assinador XML-DSig Enveloped para documentos da NFS-e Nacional."""

    def __init__(
        self,
        pfx_data: Optional[bytes] = None,
        pfx_password: Optional[str] = None,
        pfx_path: Optional[str] = None,
    ) -> None:
        if pfx_data is None and pfx_path:
            path_obj = Path(pfx_path)
            if not path_obj.exists():
                raise FileNotFoundError(f"Arquivo de certificado PFX não encontrado: {pfx_path}")
            pfx_data = path_obj.read_bytes()

        if not pfx_data:
            raise ValueError("Dados ou caminho do certificado PFX não fornecidos.")

        self.pfx_data = pfx_data
        pwd_str = pfx_password or ""
        self.pfx_password = pwd_str.encode("utf-8") if isinstance(pwd_str, str) else pwd_str
        self.private_key, self.certificate, self.ca_certs = self._extract_pfx()

    def _extract_pfx(self):
        private_key, cert, ca = pkcs12.load_key_and_certificates(self.pfx_data, self.pfx_password)
        if not private_key or not cert:
            raise ValueError("Não foi possível carregar a chave privada ou certificado do arquivo PFX informado.")
        return private_key, cert, ca

    def get_pem_private_key(self) -> bytes:
        """Retorna a chave privada em formato PEM."""
        return self.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

    def get_pem_certificate(self) -> bytes:
        """Retorna o certificado público em formato PEM."""
        return self.certificate.public_bytes(Encoding.PEM)

    def sign_xml(self, xml_raw: str, tag_to_sign: str = "infDPS") -> str:
        """Assina a tag referenciada (infDPS, infPedReg, infEvento ou infNFSe) com XML-DSig enveloped."""
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(xml_raw.encode("utf-8"), parser=parser)

        target_el = root.find(f".//{{*}}{tag_to_sign}")
        if target_el is None:
            target_el = root.find(f".//{tag_to_sign}")
        ref_id = target_el.attrib.get("Id", "") if target_el is not None else ""
        uri = f"#{ref_id}" if ref_id else ""

        try:
            from signxml import XMLSigner, methods

            class _NfseXMLSigner(XMLSigner):
                def check_deprecated_methods(self):
                    pass

            signer = _NfseXMLSigner(
                method=methods.enveloped,
                signature_algorithm="rsa-sha256",
                digest_algorithm="sha256",
                c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
            )

            signed_root = signer.sign(
                root,
                key=self.get_pem_private_key(),
                cert=self.get_pem_certificate(),
                reference_uri=uri,
            )

            # Remove quebras de linha dentro de X509Certificate, SignatureValue e DigestValue para conformidade XSD
            for node in signed_root.xpath(
                ".//*[local-name()='X509Certificate' or local-name()='SignatureValue' or local-name()='DigestValue']"
            ):
                if node.text:
                    node.text = "".join(node.text.split())

            return etree.tostring(signed_root, encoding="utf-8", xml_declaration=True).decode("utf-8")
        except Exception as exc:
            raise ValueError(f"Falha ao assinar o XML na tag '{tag_to_sign}': {exc}") from exc

    @staticmethod
    def gerar_pfx_autoassinado(
        cnpj: str = "19495981000113",
        razao_social: str = "EMPRESA TESTE LTDA",
        senha: str = "testpassword123",
    ) -> bytes:
        """Gera os bytes de um certificado PKCS#12 (.pfx) RSA-2048 autoassinado para testes e homologação."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil Teste"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"{razao_social}:{cnpj}"),
            ]
        )
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        return pkcs12.serialize_key_and_certificates(
            name=b"teste_nfse",
            key=key,
            cert=cert,
            cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(senha.encode("utf-8")),
        )
