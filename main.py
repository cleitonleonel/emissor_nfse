from core.api import EmissorNacionalNfseApi


if __name__ == "__main__":
    emissor_nacional = EmissorNacionalNfseApi(
        "user",
        "pass"
    )
    sign = emissor_nacional.auth()
    if sign:
        emissor_nacional.new_nfse()

    # Falta implementar de fato a geração da nota fiscal de serviço,
    # como não tenho cadastro em nenhuma prefeitura tive que parar
    # por aqui, caso algum interessado nessa automação tenha, favor
    # entrar em contato <cleiton.leonel@gmail.com>
    emissor_nacional.page_preview()
