from typing import Union
from core.navigator import Browser

BASE_URL = "https://www.nfse.gov.br"


class EmissorNacionalNfseApi(Browser):
    token = None

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password
        self.page_login()

    def page_login(self) -> None:
        self.response = self.send_request("GET", f"{BASE_URL}/EmissorNacional/Login", verify=False)
        self.token = self.get_soup().find("form").input["value"]

    def is_connected(self) -> Union[str, None]:
        self.response = self.send_request("GET", f"{BASE_URL}/EmissorNacional/Dashboard")
        soup = self.get_soup()
        user_profile = soup.find('li', class_='dropdown-header')
        if user_profile:
            print(user_profile.text.strip())
        return user_profile

    def auth(self) -> bool:
        if not self.username or not self.password:
            print("Usuário e senha inválidos!!!")
            exit(0)
        payload = {
            "Inscricao": self.username,
            "Senha": self.password,
            "__RequestVerificationToken": self.token
        }
        self.headers["origin"] = BASE_URL
        self.headers["referer"] = f"{BASE_URL}/EmissorNacional/Login"
        self.response = self.send_request(
            "POST",
            f"{BASE_URL}/EmissorNacional/Login",
            data=payload,
            headers=self.headers
        )
        if self.is_connected():
            return True

        print("Usuário ou senha inválidos!!!")
        return False

    def new_nfse(self) -> None:
        self.response = self.send_request(
            "GET",
            f"{BASE_URL}/EmissorNacional/DPS/Pessoas",
            headers=self.headers
        )
