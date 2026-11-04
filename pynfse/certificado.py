import os
import tempfile
from typing import Tuple

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates


class GerenciadorCertificadoA1:
    """
    Gerencia a conversão de certificados PFX (.p12/.pfx) para PEM temporários.
    Garante a exclusão segura dos arquivos do disco após o uso através de Context Manager.
    """

    def __init__(self, caminho_pfx: str, senha: str) -> None:
        """
        Args:
            caminho_pfx (str): Caminho absoluto ou relativo do arquivo .pfx
            senha (str): Senha do certificado.
        """
        self.caminho_pfx = caminho_pfx
        self.senha = senha.encode()
        self.caminho_cert_pem = ""
        self.caminho_key_pem = ""

    def __enter__(self) -> Tuple[str, str]:
        """
        Realiza a conversão e escreve os arquivos temporários.
        Returns:
            Tuple[str, str]: (Caminho do Certificado PEM, Caminho da Chave PEM)
        """
        with open(self.caminho_pfx, "rb") as arquivo_pfx:
            dados_pfx = arquivo_pfx.read()

        chave_privada, certificado, _ = load_key_and_certificates(dados_pfx, self.senha)

        if not chave_privada or not certificado:
            raise ValueError("Falha ao extrair chave privada ou certificado do arquivo PFX.")

        bytes_cert = certificado.public_bytes(Encoding.PEM)
        bytes_chave = chave_privada.private_bytes(
            Encoding.PEM,
            PrivateFormat.TraditionalOpenSSL,
            NoEncryption(),
        )

        # Usa delete=False para que requests consiga abrir o arquivo;
        # a remoção é garantida no __exit__.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_temp:
            cert_temp.write(bytes_cert)
            self.caminho_cert_pem = cert_temp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as key_temp:
            key_temp.write(bytes_chave)
            self.caminho_key_pem = key_temp.name

        return self.caminho_cert_pem, self.caminho_key_pem

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Garante a remoção dos arquivos temporários de chaves criptográficas do disco."""
        if os.path.exists(self.caminho_cert_pem):
            os.remove(self.caminho_cert_pem)
        if os.path.exists(self.caminho_key_pem):
            os.remove(self.caminho_key_pem)
