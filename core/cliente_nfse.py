import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from core.certificado import GerenciadorCertificadoA1
from bs4 import BeautifulSoup

from core.cliente_http import ClienteHttp

logger = logging.getLogger(__name__)


class EndpointsNfse:
    """Enumeração das rotas da API do Emissor Nacional de NFS-e."""
    BASE_URL = "https://www.nfse.gov.br"
    LOGIN = f"{BASE_URL}/EmissorNacional/Login"
    DASHBOARD = f"{BASE_URL}/EmissorNacional/Dashboard"
    LOGIN_CERTIFICADO = f"{BASE_URL}/EmissorNacional/Certificado"
    EMISSAO_DPS = f"{BASE_URL}/EmissorNacional/DPS/Pessoas"
    NOTAS_EMITIDAS = f"{BASE_URL}/EmissorNacional/Notas/Emitidas"
    NOTAS_RECEBIDAS = f"{BASE_URL}/EmissorNacional/Notas/Recebidas"


class FalhaAutenticacaoError(Exception):
    """Exceção levantada quando as credenciais ou certificado são inválidos."""
    pass


class ClienteNfseNacional:
    """
    Cliente para integração com o portal do Emissor Nacional de NFS-e.
    Utiliza composição com o ClienteHttp para realizar as requisições.
    """

    def __init__(self,
                 usuario: Optional[str] = None,
                 senha: Optional[str] = None,
                 caminho_pfx: Optional[str] = None,
                 senha_pfx: Optional[str] = None) -> None:
        """
        Inicializa o cliente da NFS-e.

        Args:
            usuario (str, opcional): CNPJ/CPF de acesso.
            senha (str, opcional): Senha do portal.
            caminho_pfx (str, opcional): Caminho absoluto ou relativo do arquivo .pfx.
            senha_pfx (str, opcional): Senha do arquivo .pfx.
        """
        self.http = ClienteHttp()
        self.usuario = usuario
        self.senha = senha
        self.caminho_pfx = caminho_pfx
        self.senha_pfx = senha_pfx
        self._token_csrf: Optional[str] = None
        self._tipo_consulta: Optional[str] = None
        self._preparar_diretorios()

    def _preparar_diretorios(self) -> None:
        """Cria os diretórios necessários para os downloads se não existirem."""
        Path("downloads/xmls").mkdir(parents=True, exist_ok=True)
        Path("downloads/pdfs").mkdir(parents=True, exist_ok=True)

    def _obter_token_verificacao(self) -> None:
        """Realiza requisição na página de login para extrair o RequestVerificationToken."""
        resposta = self.http.enviar_requisicao("GET", EndpointsNfse.LOGIN, verify=False)
        soup = BeautifulSoup(resposta.content, "html.parser")

        tag_form = soup.find("form")
        if tag_form:
            input_token = tag_form.find("input", {"name": "__RequestVerificationToken"})
            token_valor = input_token.get("value") if input_token else None
            if token_valor:
                self._token_csrf = str(token_valor)
                return
        else:
            raise ValueError("Não foi possível localizar o token CSRF na página de login.")

        raise ValueError("Não foi possível localizar o token CSRF na página de login.")

    def esta_autenticado(self) -> bool:
        """Verifica se a sessão atual possui acesso ao Dashboard."""
        resposta = self.http.enviar_requisicao("GET", EndpointsNfse.DASHBOARD)
        soup = BeautifulSoup(resposta.content, "html.parser")

        menu_perfil = soup.find('li', class_='dropdown perfil')
        if menu_perfil:
            perfil = menu_perfil.find("li")
            logger.info(f"Usuário logado: {perfil.text.strip()}")
            return True
        return False

    def autenticar(self) -> bool:
        """
        Realiza a autenticação no portal via Certificado Digital ou Usuário/Senha.
        
        Returns:
            bool: True se a autenticação foi bem sucedida.
            
        Raises:
            FalhaAutenticacaoError: Se as credenciais estiverem ausentes ou inválidas.
        """
        self._obter_token_verificacao()
        headers_auth = {
            "origin": EndpointsNfse.BASE_URL,
            "referer": EndpointsNfse.LOGIN
        }

        # Lógica refatorada: O context manager fica encapsulado aqui!
        if self.caminho_pfx and self.senha_pfx:
            logger.info("Autenticando via Certificado Digital...")

            # Os arquivos .pem são criados, usados no POST e imediatamente apagados do disco
            with GerenciadorCertificadoA1(self.caminho_pfx, self.senha_pfx) as cert_pem:
                self.http.enviar_requisicao(
                    "POST",
                    EndpointsNfse.LOGIN_CERTIFICADO,
                    cert=cert_pem,
                    headers=headers_auth
                )

            # Verifica se o cookie de sessão recebido é válido
            if not self.esta_autenticado():
                raise FalhaAutenticacaoError("Falha na autenticação por Certificado.")
            return True

        # Fallback para usuário e senha mantido
        if not self.usuario or not self.senha:
            raise FalhaAutenticacaoError("Credenciais não fornecidas para autenticação.")

        logger.info("Autenticando via Usuário e Senha...")
        payload = {
            "Inscricao": self.usuario,
            "Senha": self.senha,
            "__RequestVerificationToken": self._token_csrf
        }

        self.http.enviar_requisicao("POST", EndpointsNfse.LOGIN, data=payload, headers=headers_auth)

        if not self.esta_autenticado():
            raise FalhaAutenticacaoError("Falha na autenticação: Usuário ou senha incorretos.")
        return True

    def emitir_nota_simples(self, payload_dados: Dict[str, Any]) -> None:
        """
        Envia os dados de uma Declaração de Prestação de Serviço (DPS) para emitir NFS-e.
        Nota: Este método foi refatorado para receber um dicionário dinâmico.
        
        Args:
            payload_dados (Dict[str, Any]): Dicionário com os dados da nota.
        """
        self.http.enviar_requisicao(
            "POST",
            EndpointsNfse.EMISSAO_DPS,
            data=payload_dados
        )
        logger.info("Solicitação de emissão de NFS-e enviada.")

    def listar_notas_emitidas(self, data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> Dict[
        str, Any]:
        """
        Lista as notas fiscais emitidas em um período.

        Args:
            data_inicio (str, opcional): Data inicial formato DD/MM/AAAA.
            data_fim (str, opcional): Data final formato DD/MM/AAAA.

        Returns:
            Dict[str, Any]: Dicionário com chaves 'notas' (lista) ou 'erro' (string).
        """
        self._tipo_consulta = "emitidas"
        params = {}
        if data_inicio and data_fim:
            params = {
                "busca": "",
                "datainicio": data_inicio,
                "datafim": data_fim
            }

        self.http.sessao.headers.update({"Referer": EndpointsNfse.NOTAS_EMITIDAS})
        resposta = self.http.enviar_requisicao("GET", EndpointsNfse.NOTAS_EMITIDAS, params=params)
        soup = BeautifulSoup(resposta.content, "html.parser")
        corpo_tabela = soup.find("tbody")

        if not corpo_tabela:
            msg_erro_padrao = soup.find("span", {"class": "field-validation-error"})
            msg_sem_registro = soup.find("span", {"class": "sem-registros"})

            mensagem = "Erro desconhecido ao listar notas."
            if msg_erro_padrao:
                mensagem = msg_erro_padrao.get_text(strip=True)
            elif msg_sem_registro:
                mensagem = msg_sem_registro.get_text(strip=True)

            return {"notas": [], "erro": mensagem}

        linhas = corpo_tabela.find_all("tr")
        dados_notas = []

        for linha in linhas:
            div_opcoes = linha.find("div", {"class": "list-group menu-content"})
            if not div_opcoes:
                continue

            links = {
                item.get_text(strip=True).replace(" ", "_").lower(): f"{EndpointsNfse.BASE_URL}{item['href']}"
                for item in div_opcoes.find_all("a")
            }
            links.pop("cancelar_nfs-e", None)
            links.pop("substituir", None)
            dados_notas.append(links)

        return {"notas": dados_notas}

    def listar_notas_recebidas(self, data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> Dict[
        str, Any]:
        """
        Lista as notas fiscais emitidas contra um cnpj em um determinado período.

        Args:
            data_inicio (str, opcional): Data inicial formato DD/MM/AAAA.
            data_fim (str, opcional): Data final formato DD/MM/AAAA.

        Returns:
            Dict[str, Any]: Dicionário com chaves 'notas' (lista) ou 'erro' (string).
        """
        self._tipo_consulta = "recebidas"
        params = {}
        if data_inicio and data_fim:
            params = {
                "executar": "1",
                "busca": "",
                "datainicio": data_inicio,
                "datafim": data_fim
            }

        self.http.sessao.headers.update({"Referer": EndpointsNfse.NOTAS_RECEBIDAS})
        resposta = self.http.enviar_requisicao("GET", EndpointsNfse.NOTAS_RECEBIDAS, params=params)
        soup = BeautifulSoup(resposta.content, "html.parser")
        corpo_tabela = soup.find("tbody")

        if not corpo_tabela:
            msg_erro_padrao = soup.find("span", {"class": "field-validation-error"})
            msg_sem_registro = soup.find("span", {"class": "sem-registros"})

            mensagem = "Erro desconhecido ao listar notas."
            if msg_erro_padrao:
                mensagem = msg_erro_padrao.get_text(strip=True)
            elif msg_sem_registro:
                mensagem = msg_sem_registro.get_text(strip=True)

            return {"notas": [], "erro": mensagem}

        linhas = corpo_tabela.find_all("tr")
        dados_notas = []

        for linha in linhas:
            div_opcoes = linha.find("div", {"class": "list-group menu-content"})
            if not div_opcoes:
                continue

            links = {
                item.get_text(strip=True).replace(" ", "_").lower(): f"{EndpointsNfse.BASE_URL}{item['href']}"
                for item in div_opcoes.find_all("a")
            }
            links.pop("rejeitar", None)
            links.pop("confirmar", None)
            dados_notas.append(links)

        return {"notas": dados_notas}

    def _baixar_arquivo(self, url: str, diretorio_destino: str, extensao: str) -> str:
        """Método interno genérico para baixar arquivos com gerenciamento eficiente de memória."""
        nome_arquivo = f"{url.split('/')[-1]}.{extensao}"
        Path(f"{diretorio_destino}/{self._tipo_consulta}").mkdir(parents=True, exist_ok=True)
        caminho_completo = Path(f"{diretorio_destino}/{self._tipo_consulta}") / nome_arquivo

        if extensao == "xml":
            resposta = self.http.enviar_requisicao("GET", url)
            xml_bruto = re.sub(r'>\s+<', '><', resposta.text.strip())
            xml_limpo = xml_bruto.replace("&#13;", "").replace("\n", "").replace("\r", "")

            # Salva o arquivo já como texto limpo usando UTF-8 para não quebrar acentuação
            with open(caminho_completo, "w", encoding="utf-8") as arquivo:
                arquivo.write(xml_limpo)
        else:
            # Uso do bloco 'with' na requisição garantindo fechamento correto do socket
            with self.http.enviar_requisicao("GET", url, stream=True) as resposta:
                with open(caminho_completo, "wb") as arquivo:
                    for chunk in resposta.iter_content(chunk_size=8192):
                        arquivo.write(chunk)

        return str(caminho_completo)

    def baixar_xml(self, url: str, xml_path: str = "downloads/xmls") -> str:
        """Baixa o XML de uma nota e salva no disco."""
        return self._baixar_arquivo(url, xml_path, "xml")

    def baixar_pdf(self, url: str, pdf_path: str = "downloads/pdfs") -> str:
        """Baixa o PDF de uma nota e salva no disco."""
        return self._baixar_arquivo(url, pdf_path, "pdf")
