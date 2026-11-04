import os
import qrcode
import tempfile
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import json
import re
from pathlib import Path
from fpdf import FPDF
from typing import Dict, Any, Optional

NS = {"pynfse": "http://www.sped.fazenda.gov.br/nfse"}

UF_ESTADOS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"
}

def _obter_ou_baixar_logo_prefeitura(mun_nome: str, uf: str) -> Optional[Path]:
    """
    Retorna o caminho do logotipo da prefeitura no formato logo-prefeitura-{nome_municipio}.
    Se não existir localmente, tenta buscar na Wikipedia e baixar.
    """
    mun_clean = mun_nome.lower().replace(" ", "_")
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Procurar localmente nas extensões png, jpg, jpeg
    for ext in [".png", ".jpg", ".jpeg"]:
        p = assets_dir / f"logo-prefeitura-{mun_clean}{ext}"
        if p.exists():
            return p
            
    # 2. Se não existir localmente, tentar baixar da Wikipedia
    estado = UF_ESTADOS.get(uf.upper(), "")
    search_term = f"{mun_nome} {estado}"
    enc_query = urllib.parse.quote(search_term)
    url = f"https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch={enc_query}&format=json"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) EmissorNFSe/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get("query", {}).get("search", [])
            if not results:
                return None
                
            title = results[0]["title"]
            enc_title = urllib.parse.quote(title)
            page_url = f"https://pt.wikipedia.org/wiki/{enc_title}"
            
            req_page = urllib.request.Request(
                page_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) EmissorNFSe/1.0'}
            )
            with urllib.request.urlopen(req_page, timeout=5) as page_response:
                html = page_response.read().decode('utf-8')
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                infobox = soup.find('table', class_=re.compile(r'infobox|infotabela', re.I))
                if not infobox:
                    img = soup.find('img', alt=re.compile(r'brasão|brasao', re.I))
                else:
                    images = infobox.find_all('img')
                    img = None
                    for img_el in images:
                        alt = img_el.get('alt', '').lower()
                        src = img_el.get('src', '').lower()
                        if 'brasão' in alt or 'brasao' in alt or 'brasão' in src or 'brasao' in src:
                            img = img_el
                            break
                    if not img and images:
                        for img_el in images:
                            alt_l = img_el.get('alt', '').lower()
                            if 'bandeira' not in alt_l and 'localização' not in alt_l and 'mapa' not in alt_l:
                                img = img_el
                                break
                        if not img:
                            img = images[0]
                            
                if img:
                    img_src = img.get('src')
                    if img_src:
                        if img_src.startswith('//'):
                            img_url = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_url = 'https://pt.wikipedia.org' + img_src
                        else:
                            img_url = img_src
                            
                        if '/thumb/' in img_url:
                            parts = img_url.split('/')
                            img_url = '/'.join(parts[:-1]).replace('/thumb/', '/')
                            
                        # Se for SVG, obtém a versão renderizada em PNG do Wikipedia
                        if img_url.lower().endswith('.svg') and '/commons/' in img_url:
                            parts = img_url.split('/commons/')
                            filename = parts[1].split('/')[-1]
                            img_url = parts[0] + '/commons/thumb/' + parts[1] + '/500px-' + filename + '.png'
                            ext = ".png"
                        else:
                            ext = ".png" if img_url.lower().endswith(".png") else ".jpg"
                            
                        # Download do arquivo
                        req_img = urllib.request.Request(
                            img_url, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) EmissorNFSe/1.0'}
                        )
                        with urllib.request.urlopen(req_img, timeout=5) as img_response:
                            content = img_response.read()
                            logo_path = assets_dir / f"logo-prefeitura-{mun_clean}{ext}"
                            logo_path.write_bytes(content)
                            return logo_path
    except Exception as e:
        print(f"Erro ao obter brasão de {mun_nome} da Wikipedia: {e}")
        
    return None

MUNICIPIOS_IBGE = {
    "3201308": ("CARIACICA", "ES"),
    "3550308": ("SÃO PAULO", "SP"),
    "2112803": ("VIANA", "MA"),
    "3205101": ("VIANA", "ES"),
    "3205309": ("VILA VELHA", "ES"),
    "3205002": ("SERRA", "ES"),
    "3205200": ("VITÓRIA", "ES"),
}

def _find_text(root: Optional[ET.Element], xpath: str, default: str = "-") -> str:
    if root is None:
        return default
    el = root.find(xpath, NS)
    return el.text.strip() if el is not None and el.text else default

def _find_float(root: Optional[ET.Element], xpath: str) -> float:
    txt = _find_text(root, xpath, "0")
    try:
        return float(txt.replace(",", ".").strip())
    except ValueError:
        return 0.0

def format_cnpj_cpf(val: str) -> str:
    val = "".join(filter(str.isdigit, val))
    if len(val) == 14:
        return f"{val[:2]}.{val[2:5]}.{val[5:8]}/{val[8:12]}-{val[12:]}"
    elif len(val) == 11:
        return f"{val[:3]}.{val[3:6]}.{val[6:9]}-{val[9:]}"
    return val

def format_cep(val: str) -> str:
    val = "".join(filter(str.isdigit, val))
    if len(val) == 8:
        return f"{val[:5]}-{val[5:]}"
    return val

def format_phone(val: str) -> str:
    if not val or val == "-":
        return "-"
    val = "".join(filter(str.isdigit, val))
    if not val:
        return "-"
    if len(val) == 11:
        return f"({val[:2]}) {val[2:7]}-{val[7:]}"
    elif len(val) == 10:
        return f"({val[:2]}) {val[2:6]}-{val[6:]}"
    elif len(val) == 9:
        return f"{val[:5]}-{val[5:]}"
    elif len(val) == 8:
        return f"{val[:4]}-{val[4:]}"
    return val

def format_date(val: str) -> str:
    if not val or val == "-":
        return "-"
    # 2026-07-20T15:00:00-03:00 or 2026-07-20
    try:
        clean = val[:19]
        if "T" in clean:
            from datetime import datetime
            dt = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        else:
            from datetime import datetime
            dt = datetime.strptime(clean[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
    except Exception:
        return val

def format_currency(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_percent(val: float) -> str:
    return f"{val:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


class DanfsePDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(unit="mm", format="A4", *args, **kwargs)
        self.set_auto_page_break(auto=False)
        self.set_margins(left=0, top=0, right=0)
        self.add_page()

    def watermark(self, status: str):
        """Adiciona marca d'água CANCELADA ou SUBSTITUÍDA conforme item 2.5.1/2.5.2 da NT."""
        if status.upper() not in ["CANCELADA", "SUBSTITUÍDA"]:
            return
            
        self.set_font("Helvetica", "B", 50)
        self.set_text_color(220, 220, 220)  # Cinza K35 aproximado
        
        with self.rotation(angle=45, x=105, y=148):
            self.set_xy(0, 148)
            self.cell(w=210, h=10, text=status.upper(), align="C")
            
        self.set_text_color(0, 0, 0)

    def draw_field(self, label: str, value: str, x: float, y: float, w: float, h: float, align: str = "L", fill: bool = False):
        """Desenha um retângulo de campo com etiqueta e valor."""
        if fill:
            self.set_fill_color(242, 242, 242) # 5% gray density
            self.rect(x, y, w, h, style="FD")
        else:
            self.rect(x, y, w, h, style="D")
            
        # Label (5.5pt Helvetica Bold)
        self.set_font("Helvetica", "B", 5.5)
        self.set_xy(x + 1, y + 0.6)
        self.cell(w - 2, 2.0, label.upper(), border=0)
        
        # Value (7.5pt Helvetica with auto-truncation)
        self.set_font("Helvetica", "", 7.5)
        val_str = str(value)
        max_w = w - 2
        if self.get_string_width(val_str) > max_w:
            while len(val_str) > 0 and self.get_string_width(val_str + "...") > max_w:
                val_str = val_str[:-1]
            val_str = val_str + "..."
            
        y_val = y + 2.5 + (h - 6.3) * 0.5
        self.set_xy(x + 1, y_val)
        self.cell(w - 2, 3.2, val_str, border=0, align=align)

    def draw_multiline_field(self, label: str, value: str, x: float, y: float, w: float, h: float, fill: bool = False):
        """Desenha um campo com conteúdo multilinha (como descrição do serviço ou endereço)."""
        if fill:
            self.set_fill_color(242, 242, 242)
            self.rect(x, y, w, h, style="FD")
        else:
            self.rect(x, y, w, h, style="D")
            
        # Label (5.5pt Helvetica Bold)
        self.set_font("Helvetica", "B", 5.5)
        self.set_xy(x + 1, y + 0.6)
        self.cell(w - 2, 2.0, label.upper(), border=0)
        
        # Value (7.5pt Helvetica)
        self.set_font("Helvetica", "", 7.5)
        self.set_xy(x + 1, y + 2.7)
        self.multi_cell(w - 2, 3.0, str(value), border=0, align="L")


class DanfseGenerator:
    """Gerador oficial de DANFSe conforme NT 008/2026."""
    
    def __init__(self, xml_path: str, status: str = "NORMAL"):
        self.xml_path = xml_path
        self.status = status
        self.pdf = DanfsePDF()
        self.dados: Dict[str, Any] = {}
        self._parse_xml()

    def _parse_xml(self):
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
        except Exception as e:
            raise ValueError(f"Falha ao carregar XML: {e}")

        inf = root.find("pynfse:infNFSe", NS)
        if inf is None:
            inf = root

        versao = root.get("versao", "2.00")
        versao_txt = "DANFSe v1.0" if versao.startswith("1.") else "DANFSe v2.0"

        chave = inf.get("Id", "").replace("NFS", "")
        nNFSe = _find_text(inf, "pynfse:nNFSe")
        dCompet = _find_text(inf, "pynfse:dCompet")
        dhProc = _find_text(inf, "pynfse:dhProc")
        xLocEmi = _find_text(inf, "pynfse:xLocEmi", "").upper()
        
        dps = inf.find("pynfse:DPS/pynfse:infDPS", NS)
        nDPS = _find_text(dps, "pynfse:nDPS")
        serie = _find_text(dps, "pynfse:serie")
        dhEmi = _find_text(dps, "pynfse:dhEmi")
        
        emit = inf.find("pynfse:emit", NS)
        if emit is None:
            emit = dps.find("pynfse:prest", NS) if dps is not None else None
            
        cnpj_prest = _find_text(emit, "pynfse:CNPJ")
        im_prest = _find_text(emit, "pynfse:IM")
        fone_prest = _find_text(emit, "pynfse:fone")
        nome_prest = _find_text(emit, "pynfse:xNome")
        email_prest = _find_text(emit, "pynfse:email")
        
        end_prest = None
        if emit is not None:
            end_prest = emit.find("pynfse:enderNac", NS)
            if end_prest is None:
                end_prest = emit.find("pynfse:enderExt", NS)
            if end_prest is None:
                end_prest = emit.find("pynfse:end", NS)

        lgr_p = _find_text(end_prest, "pynfse:xLgr")
        if lgr_p and " - " in lgr_p and lgr_p[0].isdigit() and "-" in lgr_p.split(" - ")[0]:
            lgr_p = " - ".join(lgr_p.split(" - ")[1:])
        nro_p = _find_text(end_prest, "pynfse:nro")
        cpl_p = _find_text(end_prest, "pynfse:xCpl", "")
        bair_p = _find_text(end_prest, "pynfse:xBairro")
        
        mun_p_cod = _find_text(end_prest, "pynfse:cMun")
        if mun_p_cod == "-":
            mun_p_cod = _find_text(end_prest, "pynfse:endNac/pynfse:cMun")
        
        uf_p = _find_text(end_prest, "pynfse:UF")
        if uf_p == "-":
            uf_p = _find_text(end_prest, "pynfse:endNac/pynfse:UF")
            
        cep_p = _find_text(end_prest, "pynfse:CEP")
        if cep_p == "-":
            cep_p = _find_text(end_prest, "pynfse:endNac/pynfse:CEP")
        
        mun_p_nome = xLocEmi
        if mun_p_cod in MUNICIPIOS_IBGE:
            mun_p_nome, uf_p = MUNICIPIOS_IBGE[mun_p_cod]
        if not mun_p_nome or mun_p_nome == "-":
            mun_p_nome = "Cariacica"

        has_ibscbs = inf.find("pynfse:IBSCBS", NS) is not None



        prest_dps = dps.find("pynfse:prest", NS) if dps is not None else None
        reg_trib = prest_dps.find("pynfse:regTrib", NS) if prest_dps is not None else None
        opSimpNac = _find_text(reg_trib, "pynfse:opSimpNac")
        regApTribSN = _find_text(reg_trib, "pynfse:regApTribSN")

        toma = dps.find("pynfse:toma", NS) if dps is not None else None
        cnpj_toma = _find_text(toma, "pynfse:CNPJ")
        if cnpj_toma == "-":
            cnpj_toma = _find_text(toma, "pynfse:CPF")
        im_toma = _find_text(toma, "pynfse:IM")
        fone_toma = _find_text(toma, "pynfse:fone")
        nome_toma = _find_text(toma, "pynfse:xNome")
        email_toma = _find_text(toma, "pynfse:email")

        end_toma = toma.find("pynfse:end", NS) if toma is not None else None
        lgr_t = _find_text(end_toma, "pynfse:xLgr")
        nro_t = _find_text(end_toma, "pynfse:nro")
        cpl_t = _find_text(end_toma, "pynfse:xCpl", "")
        bair_t = _find_text(end_toma, "pynfse:xBairro")
        mun_t_cod = _find_text(end_toma, "pynfse:endNac/pynfse:cMun")
        uf_t = _find_text(end_toma, "pynfse:endNac/pynfse:UF")
        cep_t = _find_text(end_toma, "pynfse:endNac/pynfse:CEP")
        
        mun_t_nome = ""
        if mun_t_cod in MUNICIPIOS_IBGE:
            mun_t_nome, uf_t = MUNICIPIOS_IBGE[mun_t_cod]
        if not mun_t_nome or mun_t_nome == "-":
            mun_t_nome = _find_text(inf, "pynfse:xLocPrestacao", mun_t_cod)

        dest = dps.find("pynfse:dest", NS) if dps is not None else None
        cnpj_dest = _find_text(dest, "pynfse:CNPJ")
        if cnpj_dest == "-":
            cnpj_dest = _find_text(dest, "pynfse:CPF")
        fone_dest = _find_text(dest, "pynfse:fone")
        nome_dest = _find_text(dest, "pynfse:xNome")
        email_dest = _find_text(dest, "pynfse:email")
        
        end_dest = dest.find("pynfse:end", NS) if dest is not None else None
        lgr_d = _find_text(end_dest, "pynfse:xLgr")
        nro_d = _find_text(end_dest, "pynfse:nro")
        cpl_d = _find_text(end_dest, "pynfse:xCpl", "")
        bair_d = _find_text(end_dest, "pynfse:xBairro")
        mun_d_cod = _find_text(end_dest, "pynfse:endNac/pynfse:cMun")
        uf_d = _find_text(end_dest, "pynfse:endNac/pynfse:UF")
        cep_d = _find_text(end_dest, "pynfse:endNac/pynfse:CEP")
        
        mun_d_nome = ""
        if mun_d_cod in MUNICIPIOS_IBGE:
            mun_d_nome, uf_d = MUNICIPIOS_IBGE[mun_d_cod]

        interm = dps.find("pynfse:interm", NS) if dps is not None else None
        cnpj_interm = _find_text(interm, "pynfse:CNPJ")
        if cnpj_interm == "-":
            cnpj_interm = _find_text(interm, "pynfse:CPF")
        im_interm = _find_text(interm, "pynfse:IM")
        fone_interm = _find_text(interm, "pynfse:fone")
        nome_interm = _find_text(interm, "pynfse:xNome")
        email_interm = _find_text(interm, "pynfse:email")

        end_interm = interm.find("pynfse:end", NS) if interm is not None else None
        lgr_i = _find_text(end_interm, "pynfse:xLgr")
        nro_i = _find_text(end_interm, "pynfse:nro")
        cpl_i = _find_text(end_interm, "pynfse:xCpl", "")
        bair_i = _find_text(end_interm, "pynfse:xBairro")
        mun_i_cod = _find_text(end_interm, "pynfse:endNac/pynfse:cMun")
        uf_i = _find_text(end_interm, "pynfse:endNac/pynfse:UF")
        cep_i = _find_text(end_interm, "pynfse:endNac/pynfse:CEP")
        
        mun_i_nome = ""
        if mun_i_cod in MUNICIPIOS_IBGE:
            mun_i_nome, uf_i = MUNICIPIOS_IBGE[mun_i_cod]

        serv = dps.find("pynfse:serv", NS) if dps is not None else None
        cTribNac = _find_text(serv, "pynfse:cServ/pynfse:cTribNac")
        xDescServ = _find_text(serv, "pynfse:cServ/pynfse:xDescServ")
        xDescTribNac = _find_text(inf, "pynfse:xTribNac", "Serviço tributável no padrão nacional")
        
        loc_prest = serv.find("pynfse:locPrest", NS) if serv is not None else None
        cLocPrest = _find_text(loc_prest, "pynfse:cLocPrestacao", "-")
        uf_loc_prest = uf_t
        if cLocPrest in MUNICIPIOS_IBGE:
            loc_prest_nome, uf_loc_prest = MUNICIPIOS_IBGE[cLocPrest]
            loc_prest_formatado = f"{loc_prest_nome} - {uf_loc_prest}"
        else:
            loc_prest_formatado = f"{_find_text(inf, 'pynfse:xLocPrestacao', 'Viana')} - ES"
        
        valores = dps.find("pynfse:valores", NS) if dps is not None else None
        vServ = _find_float(valores, "pynfse:vServPrest/pynfse:vServ")
        vDescIncond = _find_float(valores, "pynfse:vDescCondIncond/pynfse:vDescIncond")
        vDescCond = _find_float(valores, "pynfse:vDescCondIncond/pynfse:vDescCond")
        
        trib_mun = valores.find("pynfse:trib/pynfse:tribMun", NS) if valores is not None else None
        tribISSQN = _find_text(trib_mun, "pynfse:tribISSQN")
        tpRetISSQN = _find_text(trib_mun, "pynfse:tpRetISSQN")
        is_retido = tpRetISSQN in ["1", "2"]
        vBC = _find_float(valores, "pynfse:vBC")
        pAliqAplic = _find_float(valores, "pynfse:pAliqAplic")
        vISSQN = _find_float(valores, "pynfse:vISSQN")

        vRetIRRF = _find_float(valores, "pynfse:trib/pynfse:tribFed/pynfse:vRetIRRF")
        vRetCP = _find_float(valores, "pynfse:trib/pynfse:tribFed/pynfse:vRetCP")
        vRetCSLL = _find_float(valores, "pynfse:trib/pynfse:tribFed/pynfse:vRetCSLL")
        vPis = _find_float(valores, "pynfse:trib/pynfse:tribFed/pynfse:piscofins/pynfse:vPis")
        vCofins = _find_float(valores, "pynfse:trib/pynfse:tribFed/pynfse:piscofins/pynfse:vCofins")

        vIBSMun = _find_float(inf, "pynfse:IBSCBS/pynfse:totCIBS/pynfse:gIBS/pynfse:gIBSMunTot/pynfse:vIBSMun")
        vIBSUF = _find_float(inf, "pynfse:IBSCBS/pynfse:totCIBS/pynfse:gIBS/pynfse:gIBSUFTot/pynfse:vIBSUF")
        vCBS = _find_float(inf, "pynfse:IBSCBS/pynfse:totCIBS/pynfse:gCBS/pynfse:vCBS")
        
        vTotTribFed = _find_float(valores, "pynfse:trib/pynfse:totTrib/pynfse:vTotTrib/pynfse:vTotTribFed")
        vTotTribEst = _find_float(valores, "pynfse:trib/pynfse:totTrib/pynfse:vTotTrib/pynfse:vTotTribEst")
        vTotTribMun = _find_float(valores, "pynfse:trib/pynfse:totTrib/pynfse:vTotTrib/pynfse:vTotTribMun")
        
        vLiq = _find_float(inf, "pynfse:valores/pynfse:vLiq")
        xInfComp = _find_text(dps, "pynfse:serv/pynfse:infoCompl")
        
        self.dados = {
            "versao_txt": versao_txt,
            "chave": chave,
            "nNFSe": nNFSe,
            "dCompet": format_date(dCompet),
            "dhProc": format_date(dhProc),
            "nDPS": nDPS,
            "serie": serie,
            "dhEmi": format_date(dhEmi),
            "cnpj_prest": format_cnpj_cpf(cnpj_prest),
            "im_prest": im_prest,
            "fone_prest": format_phone(fone_prest),
            "nome_prest": nome_prest,
            "email_prest": email_prest,
            "end_prest_lgr": f"{lgr_p}, {nro_p} {cpl_p} - {bair_p}",
            "end_prest_mun": f"{mun_p_nome.upper()} - {uf_p}",
            "end_prest_cep": f"{mun_p_cod} / {format_cep(cep_p)}",
            "opSimpNac": "Optante" if opSimpNac in ["1", "3"] else "Não Optante",
            "regApTribSN": "Regime de apuração dos tributos federais e municipal pelo Simples Nacional" if regApTribSN == "1" else "-",
            "mun_prest_nome": mun_p_nome,
            "uf_prest": uf_p,
            "cnpj_toma": format_cnpj_cpf(cnpj_toma) if cnpj_toma != "-" else "-",
            "im_toma": im_toma,
            "fone_toma": format_phone(fone_toma),
            "nome_toma": nome_toma,
            "email_toma": email_toma,
            "end_toma_lgr": f"{lgr_t}, {nro_t} {cpl_t} - {bair_t}" if lgr_t != "-" else "-",
            "end_toma_mun": f"{mun_t_nome} - {uf_t}" if mun_t_nome else "-",
            "end_toma_cep": f"{mun_t_cod} / {format_cep(cep_t)}" if mun_t_cod != "-" else "-",
            "cnpj_dest": format_cnpj_cpf(cnpj_dest) if cnpj_dest != "-" else "-",
            "nome_dest": nome_dest,
            "fone_dest": format_phone(fone_dest),
            "email_dest": email_dest,
            "end_dest_lgr": f"{lgr_d}, {nro_d} {cpl_d} - {bair_d}" if lgr_d != "-" else "-",
            "end_dest_mun": f"{mun_d_nome} - {uf_d}" if mun_d_nome else "-",
            "end_dest_cep": f"{mun_d_cod} / {format_cep(cep_d)}" if mun_d_cod != "-" else "-",
            "cnpj_interm": format_cnpj_cpf(cnpj_interm) if cnpj_interm != "-" else "-",
            "im_interm": im_interm,
            "nome_interm": nome_interm,
            "fone_interm": format_phone(fone_interm),
            "email_interm": email_interm,
            "end_interm_lgr": f"{lgr_i}, {nro_i} {cpl_i} - {bair_i}" if lgr_i != "-" else "-",
            "end_interm_mun": f"{mun_i_nome} - {uf_i}" if mun_i_nome else "-",
            "end_interm_cep": f"{mun_i_cod} / {format_cep(cep_i)}" if mun_i_cod != "-" else "-",
            "cTribNac": (
                (f"{cTribNac[:2]}.{cTribNac[2:4]}.{cTribNac[4:]} - " + 
                 (xDescTribNac[:35] + "..." if len(xDescTribNac) > 38 else xDescTribNac))
                if len(cTribNac) >= 6 else cTribNac
            ),
            "xDescServ": xDescServ,
            "loc_prest_formatado": loc_prest_formatado,
            "vServ": format_currency(vServ),
            "vDescIncond": format_currency(vDescIncond),
            "vDescCond": format_currency(vDescCond),
            "tribISSQN": tribISSQN,
            "vBC": format_currency(vBC),
            "pAliqAplic": format_percent(pAliqAplic),
            "vISSQN": format_currency(vISSQN),
            "vRetIRRF": format_currency(vRetIRRF),
            "vRetCP": format_currency(vRetCP),
            "vRetCSLL": format_currency(vRetCSLL),
            "vPis": format_currency(vPis),
            "vCofins": format_currency(vCofins),
            "vIBSMun": format_currency(vIBSMun),
            "vIBSUF": format_currency(vIBSUF),
            "vCBS": format_currency(vCBS),
            "vIBSTot": format_currency(vIBSMun + vIBSUF),
            "vTotTribFed": format_currency(vTotTribFed) if vTotTribFed > 0 else "-",
            "vTotTribEst": format_currency(vTotTribEst) if vTotTribEst > 0 else "-",
            "vTotTribMun": format_currency(vTotTribMun) if vTotTribMun > 0 else "-",
            "vLiq": format_currency(vLiq),
            "vTotalRet": format_currency(vRetIRRF + vRetCP + vRetCSLL + vPis + vCofins),
            "vTotNF": format_currency(vLiq + vIBSMun + vIBSUF + vCBS),
            "xInfComp": xInfComp,
            "has_ibscbs": has_ibscbs,
            "is_retido": is_retido,
            "vPisCofinsTotal": format_currency(vPis + vCofins)
        }

    def _desenhar_grid_danfse(self):
        self.pdf.set_line_width(0.35)
        self.pdf.rect(3, 3, 204, 284.7, style="D")
        self.pdf.set_line_width(0.18)

        self.pdf.rect(3, 3, 40, 11.6)
        logo_names = [
            "logo-nfs-e-horizontal.png",
            "logo-pynfse.png",
            "NFS-e.png",
            "logo-nfs-e-vertical.png",
            "logo_nfse.png"
        ]
        logo_path = None
        for name in logo_names:
            p = Path(__file__).parent / "assets" / name
            if p.exists():
                logo_path = p
                break

        if logo_path:
            is_vertical = "vertical" in logo_path.name or "logo_nfse" in logo_path.name
            if is_vertical:
                self.pdf.image(str(logo_path), x=17, y=4.3, w=12, h=9)
            elif "NFS-e.png" in logo_path.name:
                self.pdf.image(str(logo_path), x=14, y=4.0, w=18, h=9.6)
            else:
                self.pdf.image(str(logo_path), x=5, y=5.15, w=36, h=7.3)
            
        self.pdf.rect(43, 3, 101.9, 11.6)
        self.pdf.set_font("Helvetica", "B", 10)
        self.pdf.set_xy(43, 4.2)
        self.pdf.cell(101.9, 4, self.dados["versao_txt"], border=0, align="C")
        self.pdf.set_font("Helvetica", "B", 8)
        self.pdf.set_xy(43, 8.5)
        self.pdf.cell(101.9, 3.2, "Documento Auxiliar da NFS-e", border=0, align="C")
        
        mun_nome = self.dados["mun_prest_nome"].upper()
        self.pdf.rect(144.9, 3, 62.1, 11.6)
        
        # Obtém localmente ou faz download automático do brasão/logotipo da prefeitura
        uf_nome = self.dados.get("uf_prest", "ES")
        logo_pref_path = _obter_ou_baixar_logo_prefeitura(mun_nome, uf_nome)
                
        if logo_pref_path:
            # Com logo: desenha imagem à esquerda e ajusta texto à direita
            self.pdf.image(str(logo_pref_path), x=145.9, y=3.8, w=10.0, h=10.0)
            text_x = 156.9
            text_w = 49.1
        else:
            # Sem logo: texto centralizado em toda a largura
            text_x = 145.9
            text_w = 60.1
            
        self.pdf.set_font("Helvetica", "B", 8)
        self.pdf.set_xy(text_x, 3.8)
        self.pdf.cell(text_w, 4.0, f"Prefeitura Municipal de {mun_nome}", border=0, align="C")
        self.pdf.set_font("Helvetica", "", 6.5)
        self.pdf.set_xy(text_x, 7.8)
        if mun_nome == "CARIACICA":
            self.pdf.cell(text_w, 3.0, "(27) 3354-5872 | isscariacica@cariacica.es.gov.br", border=0, align="C")
        else:
            self.pdf.cell(text_w, 3.0, f"Contato: {self.dados['email_prest']}", border=0, align="C")

        self.pdf.draw_field("CHAVE DE ACESSO DA NFS-E", self.dados["chave"], 3, 14.8, 153.0, 7.7)
        
        qr_url = f"https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave={self.dados['chave']}"
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            img_qr.save(tmp_file.name)
            tmp_path = tmp_file.name
            
        self.pdf.rect(156.0, 14.8, 51.0, 21.7)
        self.pdf.image(tmp_path, x=174.25, y=15.2, w=14.5, h=14.5)
        
        self.pdf.set_font("Helvetica", "", 5)
        self.pdf.set_xy(157.0, 30.6)
        self.pdf.multi_cell(49.0, 1.6, "A autenticidade desta NFS-e pode ser verificada pela leitura deste código QR ou pela consulta da chave de acesso no portal nacional da NFS-e", border=0, align="C")
        
        try: os.unlink(tmp_path)
        except Exception: pass
 
        self.pdf.draw_field("NÚMERO DA NFS-e", self.dados["nNFSe"], 3, 22.7, 50.9, 6.7)
        self.pdf.draw_field("COMPETÊNCIA DA NFS-e", self.dados["dCompet"], 53.9, 22.7, 50.9, 6.7)
        self.pdf.draw_field("DATA E HORA DA EMISSÃO", self.dados["dhProc"], 104.8, 22.7, 51.2, 6.7)

        self.pdf.draw_field("NÚMERO DA DPS", self.dados["nDPS"], 3, 29.4, 50.9, 7.1)
        self.pdf.draw_field("SÉRIE DA DPS", self.dados["serie"], 53.9, 29.4, 50.9, 7.1)
        self.pdf.draw_field("DATA E HORA EMISSÃO DPS", self.dados["dhEmi"], 104.8, 29.4, 51.2, 7.1)

        self.pdf.draw_field("EMITENTE DA NFS-E / Prestador do Serviço", "", 3, 36.5, 50.9, 6.3, fill=True)
        self.pdf.draw_field("CNPJ / CPF / NIF", self.dados["cnpj_prest"], 53.9, 36.5, 50.9, 6.3)
        self.pdf.draw_field("INSCRIÇÃO MUNICIPAL", self.dados["im_prest"], 104.8, 36.5, 50.9, 6.3)
        self.pdf.draw_field("TELEFONE", self.dados["fone_prest"], 155.7, 36.5, 51.3, 6.3)
        
        self.pdf.draw_multiline_field("NOME / NOME EMPRESARIAL", self.dados["nome_prest"], 3, 42.8, 152.7, 6.5)
        self.pdf.draw_field("E-MAIL", self.dados["email_prest"], 155.7, 42.8, 51.3, 6.5)
        
        self.pdf.draw_multiline_field("ENDEREÇO", self.dados["end_prest_lgr"], 3, 49.3, 101.8, 6.5)
        self.pdf.draw_field("MUNICÍPIO / UF", self.dados["end_prest_mun"], 104.8, 49.3, 50.9, 6.5)
        self.pdf.draw_field("CÓDIGO IBGE / CEP", self.dados["end_prest_cep"], 155.7, 49.3, 51.3, 6.5)
        
        self.pdf.draw_field("SIMPLES NACIONAL NA COMPETÊNCIA", self.dados["opSimpNac"], 3, 55.8, 101.8, 6.5)
        self.pdf.draw_field("REGIME DE APURAÇÃO SN", self.dados["regApTribSN"], 104.8, 55.8, 102.2, 6.5)

        y_toma = 62.3
        if self.dados["cnpj_toma"] == "-":
            self.pdf.draw_field("TOMADOR DO SERVIÇO", "TOMADOR/ADQUIRENTE DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e", 3, y_toma, 204.0, 6.5, fill=True)
            toma_offset = 6.5
        else:
            self.pdf.draw_field("TOMADOR DO SERVIÇO", "", 3, y_toma, 50.9, 6.3, fill=True)
            self.pdf.draw_field("CNPJ / CPF / NIF", self.dados["cnpj_toma"], 53.9, y_toma, 50.9, 6.3)
            self.pdf.draw_field("INSCRIÇÃO MUNICIPAL", self.dados["im_toma"], 104.8, y_toma, 50.9, 6.3)
            self.pdf.draw_field("TELEFONE", self.dados["fone_toma"], 155.7, y_toma, 51.3, 6.3)
            
            self.pdf.draw_multiline_field("NOME / NOME EMPRESARIAL", self.dados["nome_toma"], 3, y_toma + 6.3, 152.7, 6.5)
            self.pdf.draw_field("E-MAIL", self.dados["email_toma"], 155.7, y_toma + 6.3, 51.3, 6.5)
            
            self.pdf.draw_multiline_field("ENDEREÇO", self.dados["end_toma_lgr"], 3, y_toma + 12.8, 101.8, 6.5)
            self.pdf.draw_field("MUNICÍPIO / UF", self.dados["end_toma_mun"], 104.8, y_toma + 12.8, 50.9, 6.5)
            self.pdf.draw_field("CÓDIGO IBGE / CEP", self.dados["end_toma_cep"], 155.7, y_toma + 12.8, 51.3, 6.5)
            toma_offset = 19.3

        y_dest = y_toma + toma_offset
        if self.dados["cnpj_dest"] == "-":
            if self.dados["cnpj_toma"] != "-":
                self.pdf.draw_field("DESTINATÁRIO DA OPERAÇÃO", "O DESTINATÁRIO É O PRÓPRIO TOMADOR/ADQUIRENTE DA OPERAÇÃO", 3, y_dest, 204.0, 6.5, fill=True)
            else:
                self.pdf.draw_field("DESTINATÁRIO DA OPERAÇÃO", "DESTINATÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e", 3, y_dest, 204.0, 6.5, fill=True)
            dest_offset = 6.5
        else:
            self.pdf.draw_field("DESTINATÁRIO DA OPERAÇÃO", "", 3, y_dest, 50.9, 6.3, fill=True)
            self.pdf.draw_field("CNPJ / CPF / NIF", self.dados["cnpj_dest"], 53.9, y_dest, 50.9, 6.3)
            self.pdf.draw_field("INSCRIÇÃO MUNICIPAL", "-", 104.8, y_dest, 50.9, 6.3)
            self.pdf.draw_field("TELEFONE", self.dados["fone_dest"], 155.7, y_dest, 51.3, 6.3)
            
            self.pdf.draw_multiline_field("NOME / NOME EMPRESARIAL", self.dados["nome_dest"], 3, y_dest + 6.3, 152.7, 6.5)
            self.pdf.draw_field("E-MAIL", self.dados["email_dest"], 155.7, y_dest + 6.3, 51.3, 6.5)
            
            self.pdf.draw_multiline_field("ENDEREÇO", self.dados["end_dest_lgr"], 3, y_dest + 12.8, 101.8, 6.5)
            self.pdf.draw_field("MUNICÍPIO / UF", self.dados["end_dest_mun"], 104.8, y_dest + 12.8, 50.9, 6.5)
            self.pdf.draw_field("CÓDIGO IBGE / CEP", self.dados["end_dest_cep"], 155.7, y_dest + 12.8, 51.3, 6.5)
            dest_offset = 19.3

        y_int = y_dest + dest_offset
        if self.dados["cnpj_interm"] == "-":
            self.pdf.draw_field("INTERMEDIÁRIO DA OPERAÇÃO", "INTERMEDIÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e", 3, y_int, 204.0, 6.5, fill=True)
            int_offset = 6.5
        else:
            self.pdf.draw_field("INTERMEDIÁRIO DA OPERAÇÃO", "", 3, y_int, 50.9, 6.3, fill=True)
            self.pdf.draw_field("CNPJ / CPF / NIF", self.dados["cnpj_interm"], 53.9, y_int, 50.9, 6.3)
            self.pdf.draw_field("INSCRIÇÃO MUNICIPAL", self.dados["im_interm"], 104.8, y_int, 50.9, 6.3)
            self.pdf.draw_field("TELEFONE", self.dados["fone_interm"], 155.7, y_int, 51.3, 6.3)
            
            self.pdf.draw_multiline_field("NOME / NOME EMPRESARIAL", self.dados["nome_interm"], 3, y_int + 6.3, 152.7, 6.5)
            self.pdf.draw_field("E-MAIL", self.dados["email_interm"], 155.7, y_int + 6.3, 51.3, 6.5)
            
            self.pdf.draw_multiline_field("ENDEREÇO", self.dados["end_interm_lgr"], 3, y_int + 12.8, 101.8, 6.5)
            self.pdf.draw_field("MUNICÍPIO / UF", self.dados["end_interm_mun"], 104.8, y_int + 12.8, 50.9, 6.5)
            self.pdf.draw_field("CÓDIGO IBGE / CEP", self.dados["end_interm_cep"], 155.7, y_int + 12.8, 51.3, 6.5)
            int_offset = 19.3

        y_serv = y_int + int_offset
        self.pdf.draw_field("SERVIÇO PRESTADO", "", 3, y_serv, 50.9, 6.3, fill=True)
        self.pdf.draw_field("CÓDIGO DE TRIBUTAÇÃO NACIONAL", self.dados["cTribNac"], 53.9, y_serv, 50.9, 6.3)
        self.pdf.draw_field("LOCAL DA PRESTAÇÃO", self.dados["loc_prest_formatado"], 104.8, y_serv, 50.9, 6.3)
        self.pdf.draw_field("PAÍS DA PRESTAÇÃO", "-", 155.7, y_serv, 51.3, 6.3)
        
        h_desc = 284.7 - 111.5 - (y_serv + 6.3)
        if h_desc < 12.0: h_desc = 12.0
            
        self.pdf.draw_multiline_field("DESCRIÇÃO DO SERVIÇO", self.dados["xDescServ"], 3, y_serv + 6.3, 204.0, h_desc)

        y_iss = y_serv + 6.3 + h_desc
        if self.dados["tribISSQN"] == "-":
            self.pdf.draw_field("TRIBUTAÇÃO MUNICIPAL (ISSQN)", "TRIBUTAÇÃO MUNICIPAL (ISSQN) - OPERAÇÃO NÃO SUJEITA AO ISSQN", 3, y_iss, 204.0, 6.5, fill=True)
            iss_offset = 6.5
        else:
            self.pdf.draw_field("TRIBUTAÇÃO DO ISSQN", "Operação Tributável", 3, y_iss, 50.9, 6.3)
            self.pdf.draw_field("PAÍS RESULTADO DA PRESTAÇÃO", "-", 53.9, y_iss, 50.9, 6.3)
            self.pdf.draw_field("MUNICÍPIO DE INCIDÊNCIA DO ISSQN", f"{mun_nome} - ES", 104.8, y_iss, 50.9, 6.3)
            self.pdf.draw_field("REGIME ESPECIAL DE TRIBUTAÇÃO", "Nenhum", 155.7, y_iss, 51.3, 6.3)
            self.pdf.draw_field("TIPO DE IMUNIDADE", "-", 3, y_iss + 6.3, 50.9, 6.3)
            self.pdf.draw_field("SUSPENSÃO DA EXIGIBILIDADE DO ISSQN", "Não", 53.9, y_iss + 6.3, 50.9, 6.3)
            self.pdf.draw_field("NÚMERO PROCESSO SUSPENSÃO", "-", 104.8, y_iss + 6.3, 50.9, 6.3)
            self.pdf.draw_field("BENEFÍCIO MUNICIPAL", "-", 155.7, y_iss + 6.3, 51.3, 6.3)
            self.pdf.draw_field("VALOR DO SERVIÇO", self.dados["vServ"], 3, y_iss + 12.6, 50.9, 6.3)
            self.pdf.draw_field("DESCONTO INCONDICIONADO", self.dados["vDescIncond"], 53.9, y_iss + 12.6, 50.9, 6.3)
            self.pdf.draw_field("TOTAL DEDUÇÕES / REDUÇÕES", "-", 104.8, y_iss + 12.6, 50.9, 6.3)
            self.pdf.draw_field("CÁLCULO DO BM", "-", 155.7, y_iss + 12.6, 51.3, 6.3)
            self.pdf.draw_field("BASE DE CÁLCULO ISSQN", self.dados["vBC"], 3, y_iss + 18.9, 50.9, 6.5)
            self.pdf.draw_field("ALÍQUOTA APLICADA", self.dados["pAliqAplic"], 53.9, y_iss + 18.9, 50.9, 6.5)
            self.pdf.draw_field("RETENÇÃO DO ISSQN", "Não Retido", 104.8, y_iss + 18.9, 50.9, 6.5)
            self.pdf.draw_field("ISSQN APURADO", self.dados["vISSQN"], 155.7, y_iss + 18.9, 51.3, 6.5)
            iss_offset = 25.4

        y_fed = y_iss + iss_offset
        self.pdf.draw_field("IRRF", self.dados["vRetIRRF"], 3, y_fed, 50.9, 6.3)
        self.pdf.draw_field("CONTRIBUIÇÃO PREVIDENCIÁRIA - RETIDA", self.dados["vRetCP"], 53.9, y_fed, 50.9, 6.3)
        self.pdf.draw_field("CONTRIBUIÇÕES SOCIAIS - RETIDAS", self.dados["vRetCSLL"], 104.8, y_fed, 50.9, 6.3)
        self.pdf.draw_field("DESCRIÇÃO CONTRIB. SOCIAIS - RETIDAS", "-", 155.7, y_fed, 51.3, 6.3)
        self.pdf.draw_field("PIS - DÉBITO APURAÇÃO PRÓPRIA", self.dados["vPis"], 3, y_fed + 6.3, 50.9, 6.5)
        self.pdf.draw_field("COFINS - DÉBITO APURAÇÃO PRÓPRIA", self.dados["vCofins"], 53.9, y_fed + 6.3, 50.9, 6.5)
        self.pdf.draw_field("DESCRIÇÃO CONTRIB. SOCIAIS RETIDAS", "-", 104.8, y_fed + 6.3, 102.2, 6.5)
        fed_offset = 12.8

        has_ibscbs = self.dados.get("has_ibscbs", False)
        y_ibs = y_fed + fed_offset
        if has_ibscbs:
            self.pdf.draw_field("CST / CCLASSTRIB", "Op. Isenta", 3, y_ibs, 50.9, 6.3)
            self.pdf.draw_field("IND. OP. / CÓD. MUNICÍPIO / SIGLA UF", "-", 53.9, y_ibs, 153.1, 6.3)
            self.pdf.draw_field("EXCLUSÕES/REDUÇÕES BC", "-", 3, y_ibs + 6.3, 50.9, 6.3)
            self.pdf.draw_field("ALÍQUOTA - CBS", "-", 53.9, y_ibs + 18.9, 50.9, 6.5)
            self.pdf.draw_field("ALÍQUOTA EFETIVA - CBS", "-", 104.8, y_ibs + 18.9, 50.9, 6.5)
            self.pdf.draw_field("VALOR TOTAL APURADO - CBS", self.dados["vCBS"], 155.7, y_ibs + 18.9, 51.3, 6.5)
            ibs_offset = 25.4
        else:
            ibs_offset = 0

        y_tot = y_ibs + ibs_offset
        if has_ibscbs:
            self.pdf.draw_field("VALOR DA OPERAÇÃO / SERVIÇO", self.dados["vServ"], 3, y_tot, 50.9, 6.7)
            self.pdf.draw_field("DESCONTO INCONDICIONADO", self.dados["vDescIncond"], 53.9, y_tot, 50.9, 6.7)
            self.pdf.draw_field("DESCONTO CONDICIONADO", self.dados["vDescCond"], 104.8, y_tot, 50.9, 6.7)
            self.pdf.draw_field("TOTAL RETENÇÕES (ISSQN/FEDERAIS)", self.dados["vTotalRet"], 155.7, y_tot, 51.3, 6.7)
            
            self.pdf.draw_field("VALOR LÍQUIDO DA NFS-E", self.dados["vLiq"], 3, y_tot + 6.7, 50.9, 6.7)
            self.pdf.draw_field("TOTAL DO IBS / CBS", self.dados["vIBSTot"], 53.9, y_tot + 6.7, 50.9, 6.7)
            self.pdf.draw_field("VALOR LÍQUIDO NFS-E + IBS/CBS", self.dados["vTotNF"], 104.8, y_tot + 6.7, 102.2, 6.7, fill=True)
        else:
            self.pdf.draw_field("VALOR DO SERVIÇO", self.dados["vServ"], 3, y_tot, 50.9, 6.7)
            self.pdf.draw_field("DESCONTO CONDICIONADO", self.dados["vDescCond"], 53.9, y_tot, 50.9, 6.7)
            self.pdf.draw_field("DESCONTO INCONDICIONADO", self.dados["vDescIncond"], 104.8, y_tot, 50.9, 6.7)
            
            vISSQN_retido = self.dados["vISSQN"] if self.dados.get("is_retido", False) else "-"
            self.pdf.draw_field("ISSQN RETIDO", vISSQN_retido, 155.7, y_tot, 51.3, 6.7)
            
            self.pdf.draw_field("TOTAL DAS RETENÇÕES FEDERAIS", self.dados["vTotalRet"], 3, y_tot + 6.7, 50.9, 6.7)
            self.pdf.draw_field("PIS/COFINS - DÉBITO APUR. PRÓPRIA", self.dados["vPisCofinsTotal"], 53.9, y_tot + 6.7, 50.9, 6.7)
            self.pdf.draw_field("VALOR LÍQUIDO DA NFS-E", self.dados["vLiq"], 104.8, y_tot + 6.7, 102.2, 6.7, fill=True)

        tot_offset = 13.4

        y_trib_aprox = y_tot + tot_offset
        self.pdf.draw_field("TRIBUTOS APROX. FEDERAIS (LEI 12.741/12)", self.dados["vTotTribFed"], 3, y_trib_aprox, 68.0, 6.5)
        self.pdf.draw_field("TRIBUTOS APROX. ESTADUAIS (LEI 12.741/12)", self.dados["vTotTribEst"], 71.0, y_trib_aprox, 68.0, 6.5)
        self.pdf.draw_field("TRIBUTOS APROX. MUNICIPAIS (LEI 12.741/12)", self.dados["vTotTribMun"], 139.0, y_trib_aprox, 68.0, 6.5)
        trib_aprox_offset = 6.5

        y_inf = y_trib_aprox + trib_aprox_offset
        self.pdf.draw_field("INFORMAÇÕES COMPLEMENTARES", "", 3, y_inf, 204.0, 4.0, fill=True)
        info_final = self.dados["xInfComp"] if self.dados["xInfComp"] != "-" else ""
        h_inf = 281.0 - (y_inf + 4.0)
        self.pdf.draw_multiline_field("", info_final, 3, y_inf + 4.0, 204.0, h_inf)

    def gerar_pdf(self, caminho_salvamento: str) -> str:
        self._desenhar_grid_danfse()
        self.pdf.watermark(self.status)
        self.pdf.output(caminho_salvamento)
        return caminho_salvamento

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        xml = sys.argv[1]
        pdf = sys.argv[2] if len(sys.argv) > 2 else "danfse.pdf"
        gen = DanfseGenerator(xml)
        gen.gerar_pdf(pdf)
        print(f"DANFSe gerada com sucesso em: {pdf}")
