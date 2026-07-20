"""Script de exemplo para autenticar no portal e baixar notas via `core`."""

import logging
import os

from dotenv import load_dotenv

from core.cliente_nfse import ClienteNfseNacional

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Opcional: Configura um logger básico para o main
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    username = os.getenv("NFSE_USUARIO")
    password = os.getenv("NFSE_SENHA")

    cert_path = os.getenv("CERTIFICADO_PATH")
    cert_senha = os.getenv("CERTIFICADO_SENHA")

    if not cert_path or not cert_senha:
        logging.warning("Variáveis para certificado não encontradas; seguindo sem certificado.")

    # Instancia a classe passando APENAS o usuário (CNPJ/CPF) e a senha.
    cliente = ClienteNfseNacional(
        usuario=username,  # Apenas números, sem pontos ou traços
        senha=password,
        caminho_pfx=cert_path,
        senha_pfx=cert_senha
    )

    try:
        # O método autenticar vai pular a lógica de certificado
        # e realizar o POST no formulário de login padrão.
        print("Iniciando login...")
        cliente.autenticar(usar_certificado=False)

        # Exibe o CNPJ autenticado
        cnpj = cliente.obter_cnpj() or "CNPJ_DESCONHECIDO"
        print(f"CNPJ autenticado: {cnpj}")
        print(f"Downloads serão salvos em: downloads/{cnpj}/")

        # A partir daqui, a sessão já está com os cookies corretos
        resultado = cliente.listar_notas_emitidas("01/09/2025", "30/09/2025", usar_adn=False)
        # resultado = cliente.listar_notas_recebidas("01/01/2026", "31/01/2026")

        if "erro" in resultado:
            print("Erro ao buscar notas:", resultado["erro"])
        else:
            print(f"Foram encontradas {len(resultado['notas'])} notas emitidas.")
            for nota in resultado["notas"]:
                situacao = nota.get("status_danfs-e")
                data_emissao = nota.get("data_emissao")
                if nota.get("download_xml"):
                    caminho = cliente.baixar_xml(nota["download_xml"], situacao, data_emissao)
                    print(f"XML Salvo em: {caminho}")
                if nota.get("download_danfs-e"):
                    caminho = cliente.baixar_pdf(nota["download_danfs-e"], situacao, data_emissao)
                    print(f"PDF Salvo em: {caminho}")

    except Exception as e:
        # Captura nossa FalhaAutenticacaoError ou erros de rede do requests
        print(f"Ocorreu uma falha no processo: {e}")


if __name__ == "__main__":
    main()
