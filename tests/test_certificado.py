from pathlib import Path

import core.certificado as certificado_module
from core.certificado import GerenciadorCertificadoA1


class FakeCertificado:
    def public_bytes(self, encoding):
        return b"-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n"


class FakeChavePrivada:
    def private_bytes(self, encoding, private_format, encryption_algorithm):
        return b"-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n"


def test_context_manager_cria_e_remove_pems(tmp_path, monkeypatch):
    caminho_pfx = tmp_path / "certificado.pfx"
    caminho_pfx.write_bytes(b"fake-pfx")

    def fake_load_key_and_certificates(dados_pfx, senha):
        assert dados_pfx == b"fake-pfx"
        assert senha == b"senha123"
        return FakeChavePrivada(), FakeCertificado(), None

    monkeypatch.setattr(
        certificado_module,
        "load_key_and_certificates",
        fake_load_key_and_certificates,
    )

    with GerenciadorCertificadoA1(str(caminho_pfx), "senha123") as (caminho_cert, caminho_key):
        assert Path(caminho_cert).exists()
        assert Path(caminho_key).exists()
        cert_text = Path(caminho_cert).read_text(encoding="utf-8")
        key_text = Path(caminho_key).read_text(encoding="utf-8")
        assert cert_text.startswith("-----BEGIN CERTIFICATE-----")
        assert key_text.startswith("-----BEGIN PRIVATE KEY-----")

    assert not Path(caminho_cert).exists()
    assert not Path(caminho_key).exists()


def test_context_manager_levanta_erro_quando_pfx_eh_invalido(tmp_path, monkeypatch):
    caminho_pfx = tmp_path / "certificado.pfx"
    caminho_pfx.write_bytes(b"fake-pfx")

    def fake_none(*args, **kwargs):
        return (None, None, None)

    monkeypatch.setattr(
        certificado_module,
        "load_key_and_certificates",
        fake_none,
    )

    try:
        with GerenciadorCertificadoA1(str(caminho_pfx), "senha123"):
            pass
    except ValueError as exc:
        assert "Falha ao extrair chave privada ou certificado" in str(exc)
    else:
        raise AssertionError("Era esperado ValueError ao processar o PFX inválido")

