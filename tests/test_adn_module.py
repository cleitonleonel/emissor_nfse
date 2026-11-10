"""Testes completos do subpacote `pynfse.adn` (Catálogos, Calculadora Tributária NT 1.101,
DPS v1.01, Eventos e101101/e105102, Validador XSD v1.01, Assinatura XML-DSig e Cliente mTLS ADN).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pynfse.adn import (
    DPS,
    AdnNfseClient,
    DpsSigner,
    Endereco,
    Intermediario,
    Prestador,
    Servico,
    Substituicao,
    Tomador,
    XsdValidator,
    build_dps_xml,
    build_evento_cancelamento_xml,
    build_evento_substituicao_xml,
    buscar_correlacoes_anexo_viii,
    calcular_tributacao,
    formatar_id_dps,
    listar_cclasstrib,
    listar_cst,
    listar_favoritos,
    listar_indop,
    listar_servicos_ctribnac,
    listar_subitens_lc116,
    obter_cclasstrib,
    obter_cst,
    obter_indop,
    obter_servico_ctribnac,
    validar_regras_ibscbs,
)


@pytest.fixture(scope="module")
def sample_pfx(tmp_path_factory) -> tuple[str, str]:
    password = "secret"
    pfx_bytes = DpsSigner.gerar_pfx_autoassinado(
        cnpj="19495981000113",
        razao_social="EMPRESA TESTE LTDA",
        senha=password,
    )
    pfx_path = tmp_path_factory.mktemp("certs") / "cert.pfx"
    pfx_path.write_bytes(pfx_bytes)
    return str(pfx_path), password


def test_pynfse_adn_catalogs_full():
    assert len(listar_cst()) == 18
    assert len(listar_cst(apenas_nfse=True)) > 5
    assert obter_cst("200") is not None
    assert len(listar_cclasstrib(apenas_nfse=False)) == 138
    assert len(listar_cclasstrib(apenas_anexo_viii=True)) == 27
    assert len(listar_servicos_ctribnac()) == 338
    assert len(listar_subitens_lc116()) > 100
    assert len(listar_indop()) == 28
    assert obter_indop("030101") is not None
    assert len(listar_favoritos()) >= 6
    assert len(buscar_correlacoes_anexo_viii(c_trib_nac="010101")) >= 1
    assert obter_cclasstrib("200029")["perc_red_ibs"] == 60.0
    assert obter_servico_ctribnac("010101")["item_lc116"] == "01.01"


def test_pynfse_adn_tax_calculator_and_validator():
    res = calcular_tributacao(
        valor_servicos=10000.0,
        ano_competencia=2026,
        regime_prestador="normal",
        aliquota_iss_informada=5.0,
        reter_federais=True,
        cClassTrib="000001",
    )
    assert res["reforma_tributaria"]["vBC"] == 9135.0
    assert res["valor_total_nf"] == res["valor_liquido"]

    # Cenário com diferimento, crédito presumido, tributação regular e compra governamental
    res_esp = calcular_tributacao(
        valor_servicos=5000.0,
        ano_competencia=2027,
        regime_prestador="normal",
        aliquota_iss_informada=2.0,
        cClassTrib="200029",
        p_ibs_uf=1.0,
        p_ibs_mun=0.5,
        p_cbs=2.0,
        p_dif_uf=10.0,
        c_cred_pres="01",
        p_cred_pres_ibs=5.0,
        p_cred_pres_cbs=5.0,
        cst_reg="000",
        c_class_trib_reg="000001",
        tp_ente_gov=1,
        p_redutor_gov=10.0,
    )
    assert res_esp["reforma_tributaria"]["credito_presumido"] is not None
    assert res_esp["reforma_tributaria"]["tributacao_regular"] is not None
    assert res_esp["reforma_tributaria"]["compras_governamentais"] is not None

    val = validar_regras_ibscbs(c_class_trib="200029", cst="000")
    assert val["valido"] is False


def test_pynfse_adn_dps_and_eventos_xsd(sample_pfx: tuple[str, str]):
    pfx_path, pfx_pwd = sample_pfx
    signer = DpsSigner(pfx_path=pfx_path, pfx_password=pfx_pwd)

    prestador = Prestador(
        cnpj="19495981000113",
        codigo_municipio="5208707",
        regime="simples",
        reg_ap_trib_sn="1",
        reg_esp_trib="0",
    )
    tomador = Tomador(
        documento="12345678000195",
        razao_social="TOMADOR TESTE LTDA",
        endereco=Endereco(
            codigo_municipio="5208707",
            cep="74805100",
            logradouro="AV T-63",
            numero="100",
            bairro="SETOR BUENO",
        ),
    )
    servico = Servico(
        codigo_municipio_prestacao="5208707",
        cTribNac="010101",
        descricao="Desenvolvimento de software",
        cNBS="115021000",
        valor=1000.00,
        cClassTrib="000001",
        indop="030101",
    )
    intermediario = Intermediario(
        documento="11222333000181",
        razao_social="INTERMEDIARIO LTDA",
    )
    substituicao = Substituicao(
        chSubstda="52087072219495981000113202604000000000000110123456",
        cMotivo="01",
        xMotivo="Retificacao de valores na nota fiscal emitida anteriormente",
    )
    trib = calcular_tributacao(
        valor_servicos=1000.00,
        regime_prestador="simples",
        cClassTrib="000001",
        cIndOp="030101",
        cTribNac="010101",
        cNBS="115021000",
    )

    dps = DPS(
        serie="900",
        numero=1,
        competencia="2026-11",
        prestador=prestador,
        tomador=tomador,
        intermediario=intermediario,
        substituicao=substituicao,
        servico=servico,
        tributacao=trib,
        ambiente="homologacao",
    )
    xml_dps = dps.to_xml()
    assert len(formatar_id_dps("5208707", "19495981000113", "900", 1)) == 45
    assert XsdValidator.validar_dps(xml_dps)["valido"] is True

    # Também valida cálculo automático de tributação pelo próprio schema DPS (sem passar tributacao explícita)
    dps_auto = DPS(
        serie="900",
        numero=2,
        prestador=prestador,
        tomador=tomador,
        servico=servico,
        ambiente="homologacao",
    )
    assert XsdValidator.validar_dps(build_dps_xml(dps_auto))["valido"] is True

    xml_dps_signed = signer.sign_xml(dps)
    assert XsdValidator.validar_dps(xml_dps_signed)["valido"] is True
    assert XsdValidator.validar_dps(dps.to_signed_xml(signer=signer))["valido"] is True

    chave = "52087072219495981000113202604000000000000110123456"
    xml_canc = build_evento_cancelamento_xml(chave_nfse=chave, documento_autor="19495981000113")
    assert XsdValidator.validar_evento(signer.sign_xml(xml_canc, tag_to_sign="infPedReg"))["valido"] is True

    chave_sub = "52087072219495981000113202604000000000000210654321"
    xml_sub = build_evento_substituicao_xml(
        chave_nfse_substituida=chave,
        chave_nfse_substituta=chave_sub,
        documento_autor="19495981000113",
    )
    assert XsdValidator.validar_evento(signer.sign_xml(xml_sub, tag_to_sign="infPedReg"))["valido"] is True


def test_adn_nfse_client_methods(sample_pfx: tuple[str, str]):
    """Testa todos os métodos do AdnNfseClient (emitir_dps, enviar_evento, consultar_nfse,
    consultar_dps, consultar_eventos, listar_dfe_adn, baixar_danfse, consultar_parametros_municipais)
    com mTLS e GZip+Base64.
    """
    pfx_path, pfx_pwd = sample_pfx
    signer = DpsSigner(pfx_path=pfx_path, pfx_password=pfx_pwd)
    client = AdnNfseClient(
        ambiente="homologacao",
        cert_pem=signer.get_pem_certificate(),
        key_pem=signer.get_pem_private_key(),
    )

    xml_original = "<NFSe><infNFSe Id='NFS123'/></NFSe>"
    b64_gz = client.compactar_xml_gzip_b64(xml_original)
    assert client.descompactar_xml_gzip_b64(b64_gz) == xml_original

    chave_teste = "32013081219495981000113000000000090226050212587505"

    async def _run_client_calls():
        mock_http_instance = AsyncMock()
        mock_http_cm = AsyncMock()
        mock_http_cm.__aenter__.return_value = mock_http_instance

        with patch("pynfse.adn.adn_client.httpx.AsyncClient", return_value=mock_http_cm):
            # 1. emitir_dps
            res_post = MagicMock()
            res_post.status_code = 201
            res_post.headers = {"content-type": "application/json"}
            res_post.json.return_value = {
                "chNFSe": chave_teste,
                "nfseXmlGZipB64": b64_gz,
            }
            mock_http_instance.post.return_value = res_post

            r_emit = await client.emitir_dps("<DPS/>")
            assert r_emit["sucesso"] is True
            assert r_emit["chave_acesso"] == chave_teste
            assert r_emit["nfse_xml"] == xml_original

            # 2. enviar_evento
            res_evt = MagicMock()
            res_evt.status_code = 200
            res_evt.headers = {"content-type": "application/json"}
            res_evt.json.return_value = {"status": "registrado"}
            mock_http_instance.post.return_value = res_evt

            r_evt = await client.enviar_evento("<pedRegEvento/>", chave_nfse=chave_teste)
            assert r_evt["sucesso"] is True

            # 3. listar_dfe_adn (migrado do antigo test_adn_client2.py)
            res_dfe = MagicMock()
            res_dfe.status_code = 200
            res_dfe.headers = {"content-type": "application/json"}
            res_dfe.json.return_value = {"LoteDFe": [{"NSU": 1}]}
            mock_http_instance.get.return_value = res_dfe

            r_dfe = await client.listar_dfe_adn(cnpj="19495981000113", ultimo_nsu=0)
            assert r_dfe["sucesso"] is True
            assert r_dfe["nsu_consultado"] == "00000000000000000000"
            assert r_dfe["dados"]["LoteDFe"][0]["NSU"] == 1

            # 4. baixar_danfse (migrado do antigo test_adn_pdf.py)
            res_pdf = MagicMock()
            res_pdf.status_code = 200
            res_pdf.headers = {"content-type": "application/pdf"}
            res_pdf.content = b"%PDF-1.4 fake pdf content"
            mock_http_instance.get.return_value = res_pdf

            r_pdf = await client.baixar_danfse(chave_teste)
            assert r_pdf["sucesso"] is True
            assert r_pdf["pdf_bytes"].startswith(b"%PDF")

            # 5. consultar_nfse, consultar_dps, consultar_eventos, consultar_parametros_municipais
            res_json = MagicMock()
            res_json.status_code = 200
            res_json.headers = {"content-type": "application/json"}
            res_json.json.return_value = {"ok": True}
            mock_http_instance.get.return_value = res_json

            assert (await client.consultar_nfse(chave_teste))["sucesso"] is True
            assert (await client.consultar_dps("DPS" + "0" * 42))["sucesso"] is True
            assert (await client.consultar_eventos(chave_teste))["sucesso"] is True
            assert (await client.consultar_parametros_municipais("3201308"))["sucesso"] is True

    asyncio.run(_run_client_calls())
