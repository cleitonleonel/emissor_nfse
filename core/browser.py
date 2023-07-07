import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

class WebScraper:
    """
    A classe WebScraper fornece uma interface para enviar solicitações HTTP e analisar a resposta usando BeautifulSoup.
    """

    def __init__(self, logger: logging.Logger):
        """
        Inicializa um objeto WebScraper.

        :param logger: Objeto logger para escrever logs de debug, informação, aviso e erro.
        """
        self.headers = self.get_headers()
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=self.get_retry_strategy()))
        self.session.mount("http://", HTTPAdapter(max_retries=self.get_retry_strategy()))
        self.logger = logger

    def get_headers(self) -> dict[str, str]:
        """
        Retorna um dicionário de cabeçalhos HTTP padrão.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/87.0.4280.88 Safari/537.36"
        }
        return headers

    def get_soup(self, url: str) -> BeautifulSoup:
        """
        Retorna um objeto BeautifulSoup analisando o conteúdo HTML da página na URL fornecida.

        :param url: URL da página a ser analisada.
        :return: Objeto BeautifulSoup representando a página.
        """
        response = self.send_request("GET", url)
        return BeautifulSoup(response.content, "html.parser")

    def send_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Envia uma solicitação HTTP para a URL fornecida e retorna a resposta.

        :param method: Método HTTP a ser usado na solicitação.
        :param url: URL para enviar a solicitação.
        :return: Resposta HTTP da solicitação.
        """
        try:
            response = self.session.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            self.logger.debug(f"{method} request to {url} returned status code {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error making {method} request to {url}: {e}")
            raise

    def get_retry_strategy(self) -> Retry:
        """
        Retorna um objeto Retry com as configurações de retentativas desejadas.
        """
        return Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504, 104],
            allowed_methods=["HEAD", "POST", "PUT", "GET", "OPTIONS"]
        )
