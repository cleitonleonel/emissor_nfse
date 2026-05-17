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
                 senha_pfx: Optional[str] = None,
                 save_path: Optional[str] = None,
                 path_structure: Optional[str] = None,
                 razao_social: Optional[str] = None) -> None:
        """
        Inicializa o cliente da NFS-e.

        Args:
            usuario (str, opcional): CNPJ/CPF de acesso.
            senha (str, opcional): Senha do portal.
            caminho_pfx (str, opcional): Caminho absoluto ou relativo do arquivo .pfx.
            senha_pfx (str, opcional): Senha do arquivo .pfx.
            save_path (str, opcional): Caminho base para salvar arquivos.
            path_structure (str, opcional): Estrutura de pastas (ex: {ANO}/{MES}).
            razao_social (str, opcional): Nome do cliente para a tag {CLIENTE}.
        """
        self.http = ClienteHttp()
        self.usuario = usuario
        self.senha = senha
        self.caminho_pfx = caminho_pfx
        self.senha_pfx = senha_pfx
        self.save_path = save_path or "downloads"
        self.path_structure = path_structure or "{CLIENTE}/{TIPO}/{ANO}/{MES}"
        self.razao_social = razao_social
        self._token_csrf: Optional[str] = None
        self._tipo_consulta: Optional[str] = None
        self._cnpj_usuario: Optional[str] = None

    def _preparar_diretorios(self) -> None:
        """Cria diretórios base legados; os downloads principais seguem `save_path` e `path_structure`."""
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
        """Verifica se a sessão atual possui acesso ao Dashboard e extrai o CNPJ."""
        resposta = self.http.enviar_requisicao("GET", EndpointsNfse.DASHBOARD)
        soup = BeautifulSoup(resposta.content, "html.parser")

        menu_perfil = soup.find('li', class_='dropdown perfil')
        if menu_perfil:
            perfil = menu_perfil.find("li")
            if perfil:
                perfil_text = perfil.text.strip()
                logger.info(f"Usuário logado: {perfil_text}")

                # Extrai o CNPJ/CPF do texto do perfil (geralmente está no início ou entre parênteses)
                # Exemplo: "19495981000113" ou "Empresa (19495981000113)"

                match = re.search(r'\d{11,14}', perfil_text)
                if match:
                    self._cnpj_usuario = match.group()
                    logger.info(f"CNPJ extraído: {self._cnpj_usuario}")

                return True
        return False

    def obter_cnpj(self) -> Optional[str]:
        """Retorna o CNPJ/CPF autenticado, se disponível."""
        if self._cnpj_usuario:
            return self._cnpj_usuario

        if self.usuario:
            apenas_digitos = re.sub(r"\D", "", self.usuario)
            if len(apenas_digitos) in (11, 14):
                return apenas_digitos

        return None

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

        self.define_tipo_consulta("emitidas")
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

            raw_status = linha.get("data-situacao", "unknown")
            status = raw_status if isinstance(raw_status, str) else str(raw_status)

            colunas = linha.find_all("td")
            data_emissao = ""
            numero = ""
            valor = "0,00"

            for col in colunas:
                txt = col.get_text(strip=True)
                # Procura Data (XX/XX/XXXX)
                if re.match(r'\d{2}/\d{2}/\d{4}', txt):
                    data_emissao = txt
                # Procura Valor (R$)
                elif "R$" in txt:
                    valor = txt
                # Procura Número (Apenas dígitos, comprimento curto)
                elif txt.isdigit() and len(txt) < 15:
                    numero = txt

            links = {
                item.get_text(strip=True).replace(" ", "_").lower(): f"{EndpointsNfse.BASE_URL}{item['href']}"
                for item in div_opcoes.find_all("a")
            }

            links.update({
                "status_danfs-e": status.split("_")[-1].lower(),
                "valor": valor,
                "data_emissao": data_emissao,
                "numero": numero
            })
            links.pop("cancelar_nfs-e", None)
            links.pop("substituir", None)

            dados_notas.append(links)

        return {"notas": dados_notas}

    def listar_notas_recebidas(self, data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> Dict[
        str, Any]:
        """
        Lista as notas fiscais emitidas contra um cnpj em um determinado período.
        """
        self.define_tipo_consulta("recebidas")
        params = {}
        if data_inicio and data_fim:
            params = {
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

            raw_status = linha.get("data-situacao", "SITUACAO_GERADA")  # Fallback para gerada em recebidas
            status = raw_status if isinstance(raw_status, str) else str(raw_status)

            colunas = linha.find_all("td")
            data_emissao = ""
            numero = ""
            valor = "0,00"

            for col in colunas:
                txt = col.get_text(strip=True)
                if re.match(r'\d{2}/\d{2}/\d{4}', txt):
                    data_emissao = txt
                elif "R$" in txt:
                    valor = txt
                elif txt.isdigit() and len(txt) < 15:
                    numero = txt

            links = {
                item.get_text(strip=True).replace(" ", "_").lower(): f"{EndpointsNfse.BASE_URL}{item['href']}"
                for item in div_opcoes.find_all("a")
            }
            links.pop("rejeitar", None)
            links.pop("confirmar", None)

            links.update({
                "status_danfs-e": status.split("_")[-1].lower(),
                "valor": valor,
                "data_emissao": data_emissao,
                "numero": numero
            })
            dados_notas.append(links)

        return {"notas": dados_notas}

    def define_tipo_consulta(self, tipo_consulta: str) -> None:
        """Define o tipo de consulta atual."""
        self._tipo_consulta = tipo_consulta

    def _baixar_arquivo(self, url: str, extensao: str, status: str = "", data_emissao: Any = None) -> str:
        """Baixa XML/PDF e grava em uma estrutura dinâmica por cliente, tipo, data, status e extensão."""
        nome_arquivo = f"{url.split('/')[-1]}.{extensao}"

        # Preparação das tags de tempo
        ano, mes, dia = "0000", "00", "00"
        if data_emissao:
            try:
                if isinstance(data_emissao, str):
                    from datetime import datetime
                    # Tenta converter diversos formatos de data comuns no portal
                    if "T" in data_emissao:
                        dt = datetime.fromisoformat(data_emissao.replace("Z", "+00:00"))
                    elif "/" in data_emissao:
                        dt = datetime.strptime(data_emissao, "%d/%m/%Y")
                    else:
                        dt = datetime.strptime(data_emissao, "%Y-%m-%d %H:%M:%S")
                    ano, mes, dia = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
                elif hasattr(data_emissao, "strftime"):
                    ano, mes, dia = (
                        data_emissao.strftime("%Y"), data_emissao.strftime("%m"), data_emissao.strftime("%d")
                    )
            except ValueError:
                pass

        # Tags disponíveis
        tags = {
            "{ANO}": ano,
            "{MES}": mes,
            "{DIA}": dia,
            "{CLIENTE}": self.razao_social or self._cnpj_usuario or "CLIENTE_DESCONHECIDO",
            "{CNPJ}": self._cnpj_usuario or "00000000000000",
            "{TIPO}": self._tipo_consulta or "outros",
            "{STATUS}": (status or "gerada").lower(),
            "{EXT}": f"{extensao}s"
        }

        # Garantia de Estrutura: Se não houver TIPO ou STATUS na máscara, forçamos a inclusão
        # para manter a organização padrão que o usuário espera
        estrutura = self.path_structure
        if "{TIPO}" not in estrutura:
            estrutura += "/{TIPO}"
        if "{STATUS}" not in estrutura:
            estrutura += "/{STATUS}"
        if "{EXT}" not in estrutura:
            estrutura += "/{EXT}"

        # Aplica as tags na estrutura
        caminho_relativo = estrutura
        for tag, val in tags.items():
            caminho_relativo = caminho_relativo.replace(tag, val)

        # Constrói o caminho final absoluto/relativo ao CWD usando Path do pathlib
        caminho_final = Path(self.save_path)
        for part in [p for p in caminho_relativo.replace("\\", "/").split("/") if p.strip()]:
            caminho_final = caminho_final / part

        caminho_final.mkdir(parents=True, exist_ok=True)
        caminho_completo = caminho_final / nome_arquivo

        try:
            if extensao.lower() == "xml":
                resposta = self.http.enviar_requisicao("GET", url)
                conteudo_xml = re.sub(r">\s+<", "><", resposta.text.strip())
                caminho_completo.write_text(conteudo_xml, encoding="utf-8")
            else:
                resposta = self.http.enviar_requisicao("GET", url, stream=True)
                with open(caminho_completo, "wb") as f:
                    for chunk in resposta.iter_content(chunk_size=8192):
                        f.write(chunk)

            logger.info(f"Arquivo salvo em: {caminho_completo}")
            return str(caminho_completo)
        except Exception as e:
            logger.error(f"Erro ao baixar {extensao}: {e}")
            return ""

    def baixar_xml(self, url: str, status: str, data_emissao: Any = None) -> str:
        """Baixa o XML de uma nota e salva no disco usando a estrutura configurada."""
        return self._baixar_arquivo(url, "xml", status, data_emissao)

    def baixar_pdf(self, url: str, status: str, data_emissao: Any = None) -> str:
        """Baixa o PDF de uma nota e salva no disco usando a estrutura configurada."""
        return self._baixar_arquivo(url, "pdf", status, data_emissao)
