import os
import logging
from dotenv import load_dotenv
from core.cliente_nfse import ClienteNfseNacional

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Opcional: Configura um logger básico para o main
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    username = os.getenv("NFSE_USUARIO")
    password = os.getenv("NFSE_SENHA")

    cert_path = None # os.getenv("CERTIFICADO_PATH")
    cert_senha = None # os.getenv("CERTIFICADO_SENHA")

    if cert_path is None or cert_senha is None:
        logging.warning("Variáveis de ambiente para certificado não encontradas. Continuando sem certificado.")

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
        cliente.autenticar()

        # A partir daqui, a sessão já está com os cookies corretos
        resultado = cliente.listar_notas_emitidas("01/09/2025", "30/09/2025")
        # resultado = cliente.listar_notas_recebidas("01/01/2026", "31/01/2026")

        if "erro" in resultado:
            print("Erro ao buscar notas:", resultado["erro"])
        else:
            print(f"Foram encontradas {len(resultado['notas'])} notas emitidas.")
            for nota in resultado["notas"]:
                situacao = nota.get("status_danfs-e")
                if nota.get("download_xml"):
                    caminho = cliente.baixar_xml(nota["download_xml"], situacao)
                    print(f"XML Salvo em: {caminho}")
                if nota.get("download_danfs-e"):
                    caminho = cliente.baixar_pdf(nota["download_danfs-e"], situacao)
                    print(f"PDF Salvo em: {caminho}")

    except Exception as e:
        # Captura nossa FalhaAutenticacaoError ou erros de rede do requests
        print(f"Ocorreu uma falha no processo: {e}")


if __name__ == "__main__":
    main()
