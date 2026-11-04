import os
import pytest
from pathlib import Path
from pynfse.danfse_generator import DanfseGenerator

def test_gerar_danfse_com_xml_real(tmp_path):
    # Procura por arquivos XML reais na pasta de downloads do nfse_manager
    caminhos_possiveis = [
        Path("../nfse_manager/downloads"),
        Path("./downloads")
    ]
    
    xml_real = None
    for caminho in caminhos_possiveis:
        if caminho.exists():
            # Busca recursiva por arquivos .xml (excluindo arquivos ocultos ou da IDE)
            arquivos = list(caminho.glob("**/*.xml"))
            # Filtra apenas os XMLs que parecem ser da NFS-e (nome do arquivo longo com a chave)
            xmls_filtrados = [f for f in arquivos if len(f.name) > 30 and not f.name.startswith(".")]
            if xmls_filtrados:
                xml_real = xmls_filtrados[0]
                break
                
    if not xml_real:
        pytest.skip("Nenhum arquivo XML real longo (chave) foi encontrado nas pastas de downloads.")
        
    print(f"Usando XML real encontrado: {xml_real}")
    
    pdf_saida = Path(__file__).parent.parent / f"danfse_real_{xml_real.stem}.pdf"
    
    # Executa o gerador com o XML real
    generator = DanfseGenerator(str(xml_real), status="NORMAL")
    generator.gerar_pdf(str(pdf_saida))
    
    # Asserções de integridade
    assert pdf_saida.exists()
    assert pdf_saida.stat().st_size > 0
    print(f"PDF gerado com sucesso a partir de XML real: {pdf_saida}")
