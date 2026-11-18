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
    catalog_updater,
    formatar_id_dps,
    listar_cclasstrib,
    listar_cst,
    listar_favoritos,
    listar_indop,
    listar_nbs,
    listar_servicos_ctribnac,
    listar_subitens_lc116,
    obter_cclasstrib,
    obter_cst,
    obter_indop,
    obter_metadados_catalogos,
    obter_nbs,
    obter_servico_ctribnac,
    set_catalogs_dir,
    validar_combinacao_nbs,
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
    assert len(listar_cclasstrib(apenas_nfse=False)) >= 138
    assert len(listar_cclasstrib(apenas_anexo_viii=True)) >= 27
    assert obter_cclasstrib("820007") is not None
    assert len(listar_servicos_ctribnac()) == 338
    assert len(listar_subitens_lc116()) > 100
    assert len(listar_indop()) >= 28
    assert obter_indop("030101") is not None
    assert obter_indop("010101") is not None
    assert len(listar_nbs()) >= 900
    assert obter_nbs("115021000") is not None
    assert len(listar_favoritos()) >= 6
    assert len(buscar_correlacoes_anexo_viii(c_trib_nac="010101")) >= 1
    assert obter_cclasstrib("200029")["perc_red_ibs"] == 60.0
    assert obter_servico_ctribnac("010101")["item_lc116"] == "01.01"

    meta = obter_metadados_catalogos()
    assert meta["totais"]["nbs"] >= 900
    assert meta["totais"]["cclasstrib"] >= 170

    val_ok = validar_combinacao_nbs("115021000", "000001", "100301")
    assert val_ok["valido"] is True
    val_bad = validar_combinacao_nbs("115021000", "999999", "999999")
    assert val_bad["valido"] is False


def test_pynfse_catalog_updater_with_override_dir(tmp_path):
    import io

    import openpyxl

    # Monta planilhas mínimas em memória simulando Anexo VII e Anexo VIII do gov.br/nfse
    wb7 = openpyxl.Workbook()
    ws7 = wb7.active
    ws7.append(["Código indOp", "Tipo de operação", "Característica do fornecimento", "Local do fornecimento a ser identificado no DFe", "Dispositivo Legal: LC 214/2025", "Observação", "indNFe", "indNFSe", "indNFSe Via", "NFSeLocIncidIBS"])
    ws7.append(["100301", "Serviço oneroso", "Local", "Domicílio", "Art. 11", "", "", "S", "", "Domicílio principal do adquirente"])
    buf7 = io.BytesIO()
    wb7.save(buf7)

    wb8 = openpyxl.Workbook()
    ws8 = wb8.active
    ws8.title = "tabela geral"
    ws8.append(["Item LC 116", "Descrição Item", "NBS", "DESCRIÇÃO NBS", "COD_ATIV_SN", "DESCRIÇÃO ATIV_SN", "INDOP", "Local incidência IBS", "cClassTrib", "nome cClassTrib"])
    ws8.append(["01.01", "Análise de sistemas", "1.1502.10.00", "Projeto e dev", "9", "Fator R", "100301", "Domicílio principal do adquirente", "000001", "Tributação integral"])
    buf8 = io.BytesIO()
    wb8.save(buf8)

    class _FakeResp:
        def __init__(self, payload=None, text="", content=b"", status_code=200):
            self._payload = payload
            self.text = text
            self.content = content
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    def _fake_get(url, headers=None, params=None, timeout=20.0):
        if "dados-abertos/versao" in url:
            return _FakeResp({"versaoDb": "V9999", "dataVersaoDb": "2026-12-01", "descricaoVersaoDb": "Teste"})
        if "situacoes-tributarias/cbs-ibs" in url:
            return _FakeResp([{"codigo": "000", "descricao": "Tributação integral", "classificacoesTributarias": [{"codigo": "000001"}]}])
        if "classificacoes-tributarias/cbs-ibs" in url:
            return _FakeResp([
                {
                    "codigo": "000001",
                    "descricao": "Tributação integral",
                    "descricaoTratamentoTributario": "Tributação integral",
                    "percentualReducaoIbsMun": 0.0,
                    "percentualReducaoCbs": 0.0,
                    "tiposDfeClassificacao": [{"sigla": "NFS-e"}],
                },
                {
                    "codigo": "820099",
                    "descricao": "Nova classificação teste",
                    "descricaoTratamentoTributario": "Teste",
                    "percentualReducaoIbsMun": 0.0,
                    "percentualReducaoCbs": 0.0,
                    "tiposDfeClassificacao": [{"sigla": "NFS-e"}],
                },
            ])
        if "nbs/lista" in url:
            return _FakeResp([
                {"codigo": "115021000", "descricao": "Dev software"},
                {"codigo": "199999999", "descricao": "NBS extra"},
            ])
        if "nfse/indicador-operacao" in url:
            return _FakeResp([{"cIndOp": "100301", "localIncidencia": "Domicílio principal do adquirente", "localFornecimento": "Domicílio", "tipoOperacao": "Serviço"}])
        if url.endswith("/rtc"):
            return _FakeResp(text='<a href="anexo_viii-tabela-correlacao-v01-03-00.xlsx">A8</a><a href="anexovii-indop_ibscbs_v1-04-00.xlsx">A7</a>')
        if "anexo_viii" in url:
            return _FakeResp(content=buf8.getvalue())
        if "anexovii" in url:
            return _FakeResp(content=buf7.getvalue())
        return _FakeResp(status_code=404)

    try:
        set_catalogs_dir(tmp_path)
        with patch.object(catalog_updater.requests.Session, "get", side_effect=_fake_get):
            res = catalog_updater.atualizar_catalogos_oficiais(destino_dir=tmp_path, force=True, validar_calculadora=False)
            assert res["atualizado"] is True
            assert res["metadados"]["versao_db"] == "V9999"
            assert res["metadados"]["usando_override_externo"] is True
            assert obter_cclasstrib("820099") is not None
            assert obter_nbs("199999999")["fonte"] == "regra_geral"

            # Segunda chamada sem force quando versão não mudou -> atualizado=False
            res2 = catalog_updater.atualizar_catalogos_oficiais(destino_dir=tmp_path, force=False, validar_calculadora=False)
            assert res2["atualizado"] is False
    finally:
        set_catalogs_dir(None)


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

            # 6. Modo XML direto (enviar_gzip_json=False) e tratamento de erro HTTP 400
            res_err = MagicMock()
            res_err.status_code = 400
            res_err.headers = {"content-type": "text/plain"}
            res_err.text = "Rejeicao E0001"
            mock_http_instance.post.return_value = res_err

            r_emit_xml = await client.emitir_dps("<DPS/>", enviar_gzip_json=False)
            assert r_emit_xml["sucesso"] is False
            assert r_emit_xml["status_code"] == 400

            r_evt_xml = await client.enviar_evento("<pedRegEvento/>", chave_nfse=chave_teste, enviar_gzip_json=False)
            assert r_evt_xml["sucesso"] is False

    asyncio.run(_run_client_calls())

    # Inicialização do AdnNfseClient diretamente via cert_path + cert_password
    client_from_pfx = AdnNfseClient(ambiente="producao", cert_path=pfx_path, cert_password=pfx_pwd)
    assert client_from_pfx.base_url.startswith("https://")


def test_pynfse_deep_coverage_builders_validators_and_danfse(sample_pfx: tuple[str, str], tmp_path):
    from pynfse import DanfseGenerator
    from pynfse.utils import (
        clean_digits,
        extrair_codigo_inicial,
        format_cep,
        format_cnpj_cpf,
        format_currency,
        format_date,
        format_percent,
        format_phone,
        parse_currency,
        parse_datetime,
    )

    # 1. Filtros combinados em catalog_service
    assert len(listar_cclasstrib(cst="200", apenas_nfse=True, q="saúde")) >= 1
    assert len(listar_servicos_ctribnac(item_lc116="01.01", q="sistemas", limite=1)) == 1
    assert obter_servico_ctribnac("999999") is None
    assert (
        len(
            buscar_correlacoes_anexo_viii(
                item_lc116="01.01",
                c_nbs="11502",
                c_class_trib="000001",
                indop="100301",
                q="desenvolvimento",
                limite=1,
            )
        )
        == 1
    )

    # 2. Tax calculator overrides e todas as regras de validação IBS/CBS
    res_full = calcular_tributacao(
        valor_servicos=10000.0,
        data_competencia="15/05/2026",
        regime_prestador="simples",
        apurar_ibscbs_simples=True,
        cClassTrib="200029",
        aliquota_iss_informada=3.0,
        iss_retido=True,
        reter_federais=True,
        v_pis_informado=50.0,
        v_cofins_informado=200.0,
        v_irrf_informado=150.0,
        v_csll_informado=100.0,
        v_inss_informado=110.0,
        p_ibs_uf=1.0,
        p_ibs_mun=0.5,
        p_cbs=2.0,
        p_red_aliq_uf=50.0,
        p_red_aliq_mun=50.0,
        p_red_aliq_cbs=50.0,
        p_dif_uf=10.0,
        p_dif_mun=10.0,
        p_dif_cbs=10.0,
        c_cred_pres="01",
        cst_reg="000",
        c_class_trib_reg="000001",
        tp_ente_gov=1,
        p_redutor_gov=10.0,
        v_ibs_est_cred=5.0,
        v_cbs_est_cred=10.0,
        ind_doacao=1,
    )
    assert res_full["retencoes_federais"]["irrf"] == 150.0
    assert res_full["reforma_tributaria"]["ibs_uf"]["vDifUF"] > 0
    res_full["v_tot_trib"] = {"fed": 100.0, "est": 20.0, "mun": 50.0}

    # Constrói DPS com todos os campos opcionais de servico, retenções federais e grupos IBSCBS
    xml_dps_full = build_dps_xml(
        prestador={
            "cnpj": "19495981000113",
            "inscricao_municipal": "12345",
            "codigo_municipio": "3201308",
            "regime": "normal",
            "fone": "2733334444",
            "email": "fiscal@empresa.com",
        },
        tomador={
            "documento": "12345678901",
            "razao_social": "TOMADOR PF COMPLETO",
            "inscricao_municipal": "999",
            "fone": "27999998888",
            "email": "pf@cliente.com",
            "endereco": {
                "codigo_municipio": "3201308",
                "cep": "29140000",
                "logradouro": "AV CENTRAL",
                "numero": "10",
                "complemento": "APTO 101",
                "bairro": "CENTRO",
            },
        },
        servico={
            "codigo_municipio_prestacao": "3201308",
            "cTribNac": "010101",
            "cTribMun": "001",
            "descricao": "Desenvolvimento completo",
            "cNBS": "115021000",
            "cIntContrib": "SRV-001",
            "idDocTec": "ART-123",
            "docRef": "CONTRATO-2026",
            "xInfComp": "Informacoes complementares da nota",
            "valor": 10000.0,
            "valor_recebido": 9500.0,
            "desconto_incondicionado": 100.0,
            "desconto_condicionado": 50.0,
            "cClassTrib": "200029",
            "indop": "100301",
            "indFinal": 1,
            "tpOper": 1,
            "refNFSe": ["32013082219495981000113202604000000000000110123456"],
            "tpEnteGov": 1,
            "cCredPres": "01",
            "tributacao_regular": {"CSTReg": "000", "cClassTribReg": "000001"},
        },
        tributacao=res_full,
        serie_dps="900",
        numero_dps=55,
        ambiente="producao",
    )
    assert "<tribFed>" in xml_dps_full
    assert "<gTribRegular>" in xml_dps_full
    assert "<gDif>" in xml_dps_full
    assert "<infoCompl>" in xml_dps_full

    val_errs = validar_regras_ibscbs(
        c_class_trib="000001",
        cst="000",
        c_ind_op="999999",
        tp_oper=2,
        tem_ref_nfse=False,
        ind_dest=0,
        tem_destinatario=True,
        tp_ente_gov=9,
        p_dif_uf=10.0,
    )
    assert val_errs["valido"] is False
    assert len(val_errs["erros"]) >= 3

    # 3. Evento builder validações de erro e autor CPF
    with pytest.raises(ValueError):
        build_evento_cancelamento_xml(chave_nfse="123", documento_autor="19495981000113")
    with pytest.raises(ValueError):
        build_evento_cancelamento_xml(chave_nfse="1" * 50, documento_autor="123")
    with pytest.raises(ValueError):
        build_evento_cancelamento_xml(chave_nfse="1" * 50, documento_autor="19495981000113", motivo_descricao="curto")

    xml_canc_cpf = build_evento_cancelamento_xml(
        chave_nfse="52087072219495981000113202604000000000000110123456",
        documento_autor="12345678901",
    )
    assert "<CPFAutor>12345678901</CPFAutor>" in xml_canc_cpf

    # 4. XsdValidator com XML malformado e validar_nfse
    assert XsdValidator.validar_dps("<xml_invalido")["valido"] is False
    assert XsdValidator.validar_evento("<xml_invalido")["valido"] is False
    assert XsdValidator.validar_nfse("<xml_invalido")["valido"] is False

    # 5. DanfseGenerator com marca d'água CANCELADA e SUBSTITUÍDA
    xml_nfse_sample = """<?xml version="1.0" encoding="utf-8"?>
    <NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
      <infNFSe Id="NFS32013082219495981000113202604000000000000110123456">
        <xLocEmi>Cariacica</xLocEmi>
        <xLocPrestacao>Cariacica</xLocPrestacao>
        <nNFSe>1</nNFSe>
        <cLocIncid>3201308</cLocIncid>
        <xLocIncid>Cariacica</xLocIncid>
        <xTribNac>Análise e desenvolvimento de sistemas</xTribNac>
        <xNBS>Serviços de desenvolvimento de software</xNBS>
        <verAplic>1.0</verAplic>
        <ambGer>2</ambGer>
        <tpEmis>1</tpEmis>
        <procEmi>1</procEmi>
        <cStat>100</cStat>
        <dhProc>2026-04-15T10:30:00-03:00</dhProc>
        <nDFSe>1</nDFSe>
        <emit>
          <CNPJ>19495981000113</CNPJ>
          <xNome>EMPRESA TESTE LTDA</xNome>
          <enderNac><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><cMun>3201308</cMun><UF>ES</UF><CEP>29140000</CEP></enderNac>
        </emit>
        <valores>
          <vBC>1000.00</vBC><pAliqAplic>2.00</pAliqAplic><vISSQN>20.00</vISSQN><vLiq>1000.00</vLiq>
        </valores>
        <DPS versao="1.01">
          <infDPS Id="DPS320130821949598100011300900000000000000001">
            <tpAmb>2</tpAmb><dhEmi>2026-04-15T10:29:00-03:00</dhEmi><verAplic>1.0</verAplic><serie>900</serie><nDPS>1</nDPS><dCompet>2026-04-15</dCompet><tpEmit>1</tpEmit><cLocEmi>3201308</cLocEmi>
            <prest><CNPJ>19495981000113</CNPJ><regTrib><opSimpNac>3</opSimpNac><regApTribSN>1</regApTribSN><regEspTrib>0</regEspTrib></regTrib></prest>
            <toma><CPF>12345678901</CPF><xNome>CLIENTE PF</xNome></toma>
            <serv><locPrest><cLocPrestacao>3201308</cLocPrestacao></locPrest><cServ><cTribNac>010101</cTribNac><xDescServ>Servico completo</xDescServ><cNBS>115021000</cNBS></cServ></serv>
            <valores><vServPrest><vServ>1000.00</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN><pAliq>2.00</pAliq></tribMun><totTrib><indTotTrib>0</indTotTrib></totTrib></trib></valores>
          </infDPS>
        </DPS>
      </infNFSe>
    </NFSe>"""
    pdf_canc = tmp_path / "danfse_cancelada.pdf"
    DanfseGenerator(xml_nfse_sample, status="CANCELADA").gerar_pdf(str(pdf_canc))
    assert pdf_canc.exists()

    # 6. Utils helpers
    assert clean_digits("12.345-6") == "123456"
    assert format_cnpj_cpf("12345678901") == "123.456.789-01"
    assert format_cnpj_cpf("19495981000113") == "19.495.981/0001-13"
    assert format_cep("29140000") == "29140-000"
    assert format_phone("27999998888") == "(27) 99999-8888"
    assert format_phone("2733334444") == "(27) 3333-4444"
    assert format_currency(1234.56) == "R$ 1.234,56"
    assert parse_currency("R$ 1.234,56") == 1234.56
    assert format_percent(5.5) == "5,50%"
    assert extrair_codigo_inicial("1 - Operação Normal") == "1"
    assert parse_datetime("15/04/2026 às 10:20:30") is not None
    assert format_date("2026-04-15", include_time=False) == "15/04/2026"

    # 7. ClienteNfseNacional (_requisicao_adn, salvar_xml_adn, obter_impressao_html, _listar_notas_adn)
    import base64
    import gzip
    import json

    from pynfse import ClienteNfseNacional
    from pynfse.danfse_generator import _obter_ou_baixar_logo_prefeitura

    pfx_path, pfx_pwd = sample_pfx
    cli_nac = ClienteNfseNacional(
        usuario="19495981000113",
        senha="123",
        caminho_pfx=pfx_path,
        senha_pfx=pfx_pwd,
        save_path=str(tmp_path),
    )
    saved_xml = cli_nac.salvar_xml_adn(
        xml_nfse_sample.encode("utf-8"),
        "32013082219495981000113202604000000000000110123456",
        "gerada",
    )
    assert saved_xml.endswith(".xml")

    # Testar obter_impressao_html
    mock_vis_resp = MagicMock()
    mock_vis_resp.content = b'<html><body><a href="/EmissorNacional/Notas/Visualizar/Impressao/123">Imp</a></body></html>'
    mock_imp_resp = MagicMock()
    mock_imp_resp.text = "<html><body>Impressao OK</body></html>"
    with patch.object(cli_nac.http, "enviar_requisicao", side_effect=[mock_vis_resp, mock_imp_resp]):
        html_obtido = cli_nac.obter_impressao_html("32013082219495981000113202604000000000000110123456")
        assert html_obtido == "<html><body>Impressao OK</body></html>"

    # Testar _listar_notas_adn com lote GZip+Base64
    gz_b64 = base64.b64encode(gzip.compress(xml_nfse_sample.encode("utf-8"))).decode("ascii")
    mock_adn_resp1 = MagicMock()
    mock_adn_resp1.json.return_value = {"LoteDFe": [{"NSU": 10, "ArquivoXml": gz_b64}]}
    mock_adn_resp2 = MagicMock()
    mock_adn_resp2.json.return_value = {"LoteDFe": []}
    with patch.object(cli_nac, "_requisicao_adn", side_effect=[mock_adn_resp1, mock_adn_resp2]):
        res_adn_list = cli_nac._listar_notas_adn("emitidas", "01/04/2026", "30/04/2026")
        assert len(res_adn_list["notas"]) == 1

    # Testar _requisicao_adn com mock de requests.request
    mock_req_ok = MagicMock(status_code=200)
    with (
        patch("requests.request", return_value=mock_req_ok),
        patch("time.sleep"),
    ):
        r_req = cli_nac._requisicao_adn("GET", "https://adn.nfse.gov.br/teste", headers={"X-Test": "1"})
        assert r_req.status_code == 200

    # Testar _obter_brasao_municipio com mock de urllib.request.urlopen
    wiki_search_json = json.dumps({"query": {"search": [{"title": "Município Teste"}]}}).encode("utf-8")
    wiki_page_html = (
        b'<table class="infobox"><img alt="Bras\xc3\xa3o" '
        b'src="//upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Brasao.svg/200px-Brasao.svg.png"/></table>'
    )
    fake_png = b"\x89PNG\r\n\x1a\nfake"

    def _fake_urlopen(req, timeout=5):
        cm = MagicMock()
        u = req.full_url if hasattr(req, "full_url") else str(req)
        if "api.php" in u:
            cm.__enter__.return_value.read.return_value = wiki_search_json
        elif "/wiki/" in u:
            cm.__enter__.return_value.read.return_value = wiki_page_html
        else:
            cm.__enter__.return_value.read.return_value = fake_png
        return cm

    with (
        patch("urllib.request.urlopen", side_effect=_fake_urlopen),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
    ):
        brasao = _obter_ou_baixar_logo_prefeitura("CidadeFicticiaTeste", "ES")
        assert brasao is not None

    # 8. Testa transição de layout NT 004 v2.0 <-> NT 009 v1.01, validação XSD dual e auto-fallback em E1235
    from pynfse.adn import converter_xml_dps_layout_nt

    xml_nt004 = build_dps_xml(
        prestador={"cnpj": "19495981000113", "codigo_municipio": "3201308", "regime": "simples"},
        tomador={"documento": "33335146000147", "razao_social": "AT DISTRIBUIDORA"},
        servico={"cTribNac": "010701", "cNBS": "115013000", "descricao": "SUPORTE TI", "valor": 1.0, "aliquota_iss": 5.0},
        versao_nt="nt004",
    )
    assert "<pTotTribSN>5.00</pTotTribSN>" in xml_nt004
    assert "<pAliq>" not in xml_nt004
    assert "<gIBSCBS>" in xml_nt004
    assert XsdValidator.validar_dps(xml_nt004)["valido"] is True

    xml_nt009 = build_dps_xml(
        prestador={"cnpj": "19495981000113", "codigo_municipio": "3201308", "regime": "simples"},
        tomador={"documento": "33335146000147", "razao_social": "AT DISTRIBUIDORA"},
        servico={"cTribNac": "010701", "cNBS": "115013000", "descricao": "SUPORTE TI", "valor": 1.0, "aliquota_iss": 5.0},
        versao_nt="nt009",
    )
    assert "<gIBSCBS>" not in xml_nt009
    assert xml_nt009.index("<cNBS>") < xml_nt009.index("<xDescServ>")
    assert xml_nt009.index("<finNFSe>") < xml_nt009.index("<cLocEmi>")
    assert XsdValidator.validar_dps(xml_nt009)["valido"] is True

    # Conversão bidirecional preserva integridade XSD
    xml_back_to_004 = converter_xml_dps_layout_nt(xml_nt009, para_nt009=False)
    assert "<gIBSCBS>" in xml_back_to_004
    assert XsdValidator.validar_dps(xml_back_to_004)["valido"] is True

    # Auto-fallback no AdnNfseClient quando a Sefin retorna E1235
    signer_fb = DpsSigner(pfx_path=pfx_path, pfx_password=pfx_pwd)
    client_fb = AdnNfseClient(
        ambiente="homologacao",
        cert_pem=signer_fb.get_pem_certificate(),
        key_pem=signer_fb.get_pem_private_key(),
    )
    chave_fb = "32013082219495981000113000000000000126110047192931"

    async def _test_e1235_autofallback():
        mock_http_instance = AsyncMock()
        mock_http_cm = AsyncMock()
        mock_http_cm.__aenter__.return_value = mock_http_instance

        res_e1235 = MagicMock()
        res_e1235.status_code = 400
        res_e1235.headers = {"content-type": "application/json"}
        res_e1235.json.return_value = {
            "erros": [
                {
                    "Codigo": "E1235",
                    "Descricao": "Falha no esquema XML do DF-e.",
                    "Complemento": "The element 'infDPS' has invalid child element 'cLocEmi'. Expected: 'finNFSe'.",
                }
            ]
        }
        res_ok = MagicMock()
        res_ok.status_code = 201
        res_ok.headers = {"content-type": "application/json"}
        res_ok.json.return_value = {"chaveAcesso": chave_fb}
        mock_http_instance.post.side_effect = [res_e1235, res_ok]

        with patch("pynfse.adn.adn_client.httpx.AsyncClient", return_value=mock_http_cm):
            signed_004 = signer_fb.sign_xml(xml_nt004, tag_to_sign="infDPS")
            ret = await client_fb.emitir_dps(signed_004)
            assert ret["sucesso"] is True
            assert ret["chave_acesso"] == chave_fb
            assert mock_http_instance.post.call_count == 2
            assert "<gIBSCBS>" not in ret["dps_xml_assinado"]

    asyncio.run(_test_e1235_autofallback())
