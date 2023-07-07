import urllib3
import requests
import tempfile
import webbrowser
from typing import Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

urllib3.disable_warnings()

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504, 104],
    allowed_methods=["HEAD", "POST", "PUT", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)


class Browser(object):

    def __init__(self):
        self.response = None
        self.headers = self.get_headers()
        self.session = requests.Session()

    def get_headers(self) -> Dict[str, str]:
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/87.0.4280.88 Safari/537.36"
        }
        return self.headers

    def get_soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.response.content, "html.parser")

    def page_preview(self) -> None:
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".html") as file:
            file.write(self.response.content)
        webbrowser.open_new_tab(f"file://{file.name}")

    def send_request(self, method: str, url: str, **kwargs) -> requests.Response:
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        return self.session.request(method, url, **kwargs)
