import logging
from typing import Any, Dict

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Desabilita avisos de InsecureRequestWarning caso use verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class ClienteHttp:
    """
    Cliente HTTP resiliente baseado em requests.Session.
    Configurado nativamente com estratégias de retry para lidar com instabilidades de rede.
    """

    def __init__(self) -> None:
        """Inicializa a sessão HTTP e monta os adaptadores de retry."""
        self.sessao = requests.Session()
        self.sessao.headers.update(self._obter_headers_padrao())
        self._configurar_retries()

    def _obter_headers_padrao(self) -> Dict[str, str]:
        """Retorna os cabeçalhos padrão para simular um navegador comum."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def _configurar_retries(self) -> None:
        """Configura a política de retentativas (retry) para falhas transitórias."""
        estrategia_retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504, 104],
            allowed_methods=["HEAD", "POST", "PUT", "GET", "OPTIONS"]
        )
        adaptador = HTTPAdapter(max_retries=estrategia_retry)
        self.sessao.mount("https://", adaptador)
        self.sessao.mount("http://", adaptador)

    def enviar_requisicao(self, metodo: str, url: str, **kwargs: Any) -> requests.Response:
        """
        Envia uma requisição HTTP.

        Como retorna um requests.Response, suporta uso de context managers (with)
        quando kwargs contiver stream=True.

        Args:
            metodo (str): Método HTTP ('GET', 'POST', etc.).
            url (str): URL de destino.
            **kwargs: Argumentos adicionais repassados para requests.Session.request.

        Returns:
            requests.Response: Resposta da requisição.
        """
        try:
            resposta = self.sessao.request(metodo, url, **kwargs)
            resposta.raise_for_status()
            return resposta
        except requests.RequestException as e:
            logger.error(f"Erro na requisição {metodo} {url}: {e}")
            raise
