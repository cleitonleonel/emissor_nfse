from pynfse.danfse_generator import DanfseGenerator

NS = "http://www.sped.fazenda.gov.br/nfse"


def test_gerar_danfse_completa(tmp_path):
    xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<CompNfse xmlns="{NS}">
  <infNFSe Id="NFS32013082253890961000185000000000002126019913119917">
    <nNFSe>12345</nNFSe>
    <dCompet>2026-07-20</dCompet>
    <dhProc>2026-07-20T15:30:00-03:00</dhProc>
    <cStat>1</cStat>
    <DPS>
      <infDPS>
        <nDPS>9988</nDPS>
        <serie>1</serie>
        <dhEmi>2026-07-20T15:00:00-03:00</dhEmi>
        <prest>
          <CNPJ>12345678000199</CNPJ>
          <IM>998877</IM>
          <fone>11999998888</fone>
          <xNome>EMPRESA PRESTADORA DE SERVICOS LTDA</xNome>
          <email>financeiro@prestadora.com.br</email>
          <end>
            <xLgr>Avenida Paulista</xLgr>
            <nro>1000</nro>
            <xCpl>Conjunto 50</xCpl>
            <xBairro>Bela Vista</xBairro>
            <endNac>
              <cMun>3550308</cMun>
              <UF>SP</UF>
              <CEP>01310100</CEP>
            </endNac>
          </end>
          <regTrib>
            <opSimpNac>1</opSimpNac>
            <regApTribSN>1</regApTribSN>
          </regTrib>
        </prest>
        <toma>
          <CNPJ>98765432000188</CNPJ>
          <IM>112233</IM>
          <fone>11988887777</fone>
          <xNome>EMPRESA TOMADORA DE SERVICOS S/A</xNome>
          <email>recepcao@tomadora.com.br</email>
          <end>
            <xLgr>Rua Haddock Lobo</xLgr>
            <nro>500</nro>
            <xBairro>Cerqueira Cesar</xBairro>
            <endNac>
              <cMun>3550308</cMun>
              <UF>SP</UF>
              <CEP>01414001</CEP>
            </endNac>
          </end>
        </toma>
        <serv>
          <cServ>
            <cTribNac>1.05</cTribNac>
            <xDescServ>Licenciamento e cessao de direito de uso de programas de computacao
            padronizados ou customizados, incluindo suporte tecnico, atualizacao e
            outras manutencoes corretivas ou preventivas.</xDescServ>
          </cServ>
          <infoCompl>Nota fiscal de teste para homologacao do emissor nacional de NFS-e.</infoCompl>
        </serv>
        <valores>
          <vServPrest>
            <vServ>1500.00</vServ>
          </vServPrest>
          <vDescCondIncond>
            <vDescIncond>100.00</vDescIncond>
            <vDescCond>0.00</vDescCond>
          </vDescCondIncond>
          <vBC>1400.00</vBC>
          <pAliqAplic>2.00</pAliqAplic>
          <vISSQN>28.00</vISSQN>
          <trib>
            <tribFed>
              <vRetIRRF>15.00</vRetIRRF>
              <vRetCP>20.00</vRetCP>
              <vRetCSLL>10.00</vRetCSLL>
              <piscofins>
                <vPis>5.00</vPis>
                <vCofins>25.00</vCofins>
              </piscofins>
            </tribFed>
          </trib>
        </valores>
      </infDPS>
    </DPS>
    <valores>
      <vLiq>1428.00</vLiq>
    </valores>
    <IBSCBS>
      <totCIBS>
        <gIBS>
          <gIBSMunTot>
            <vIBSMun>14.00</vIBSMun>
          </gIBSMunTot>
          <gIBSUFTot>
            <vIBSUF>21.00</vIBSUF>
          </gIBSUFTot>
        </gIBS>
        <gCBS>
          <vCBS>15.00</vCBS>
        </gCBS>
      </totCIBS>
    </IBSCBS>
  </infNFSe>
</CompNfse>
"""
    xml_path = tmp_path / "nfse_teste.xml"
    xml_path.write_text(xml_content, encoding="utf-8")

    pdf_path = tmp_path / "danfse_teste.pdf"

    # 1. Instanciar o gerador com a nota normal
    generator = DanfseGenerator(str(xml_path), status="NORMAL")
    generator.gerar_pdf(str(pdf_path))

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0

    # 2. Instanciar o gerador com a nota cancelada
    pdf_cancelada_path = tmp_path / "danfse_cancelada.pdf"
    generator_cancelada = DanfseGenerator(str(xml_path), status="CANCELADA")
    generator_cancelada.gerar_pdf(str(pdf_cancelada_path))

    assert pdf_cancelada_path.exists()
    assert pdf_cancelada_path.stat().st_size > 0

    print("Testes da DanfseGenerator executados com sucesso!")
