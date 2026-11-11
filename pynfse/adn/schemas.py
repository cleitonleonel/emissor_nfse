"""Schemas Pydantic v2 para construção e validação de DPS v1.01 no padrão ADN / Sefin Nacional.

Permite instanciar `Endereco`, `Prestador`, `Tomador`, `Servico`, `Intermediario`, `Substituicao`
e `DPS` diretamente como objetos tipados e validados pelo Pydantic (sem necessidade de converter
para dicionários), mantendo aceitação automática de `dict` via `model_validate`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from pynfse.utils import clean_digits as _clean_digits


class Endereco(BaseModel):
    """Schema de endereço nacional do Prestador ou Tomador."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    logradouro: Optional[str] = None
    numero: str = "S/N"
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    codigo_municipio: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None

    @field_validator("codigo_municipio", mode="before")
    @classmethod
    def _norm_cmun(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return _clean_digits(v).zfill(7)[:7]

    @field_validator("cep", mode="before")
    @classmethod
    def _norm_cep(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return _clean_digits(v).zfill(8)[:8]


class Substituicao(BaseModel):
    """Schema do grupo `<subst>` (Substituição de NFS-e via DPS v1.01)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    chSubstda: str = Field(validation_alias=AliasChoices("chSubstda", "chave_substituida"))
    cMotivo: str = Field(default="99", validation_alias=AliasChoices("cMotivo", "codigo_motivo"))
    xMotivo: Optional[str] = Field(default=None, validation_alias=AliasChoices("xMotivo", "descricao_motivo"))

    @field_validator("chSubstda", mode="before")
    @classmethod
    def _val_chave(cls, v: Any) -> str:
        ch = _clean_digits(v)
        if len(ch) != 50:
            raise ValueError(
                f"Chave da NFS-e a ser substituída (chSubstda) deve ter 50 dígitos (informado: {len(ch)})."
            )
        return ch

    @field_validator("cMotivo", mode="before")
    @classmethod
    def _val_cmotivo(cls, v: Any) -> str:
        cod = str(v or "99").strip().zfill(2)
        if cod not in {"01", "02", "03", "04", "05", "99"}:
            raise ValueError(f"cMotivo de substituição inválido: '{cod}'. Use 01, 02, 03, 04, 05 ou 99.")
        return cod

    @model_validator(mode="after")
    def _val_xmotivo_obrigatorio(self) -> Substituicao:
        motivo_txt = (self.xMotivo or "").strip()
        if self.cMotivo == "99" and len(motivo_txt) < 15:
            raise ValueError(
                "Para substituição com cMotivo='99' (Outros), xMotivo é obrigatório (mínimo 15 caracteres)."
            )
        self.xMotivo = motivo_txt if motivo_txt else None
        return self


class Prestador(BaseModel):
    """Schema do Prestador de Serviços (`<prest>`) da DPS v1.01."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    documento: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    razao_social: Optional[str] = None
    codigo_municipio: str = "3201308"
    endereco: Optional[Endereco] = None
    regime: str = Field(default="normal", validation_alias=AliasChoices("regime", "regime_tributario"))
    reg_ap_trib_sn: str = Field(default="1", validation_alias=AliasChoices("reg_ap_trib_sn", "regime_apuracao_sn"))
    reg_esp_trib: str = Field(default="0", validation_alias=AliasChoices("reg_esp_trib", "regime_especial"))
    email: Optional[str] = None
    fone: Optional[str] = Field(default=None, validation_alias=AliasChoices("fone", "telefone"))
    tp_emit: str = "1"
    c_motivo_emis_ti: Optional[str] = None
    ch_nfse_rej: Optional[str] = None
    incluir_xnome_dps: bool = False
    ambiente: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_endereco_municipio(cls, data: Any) -> Any:
        if isinstance(data, dict):
            end = data.get("endereco")
            if end and not data.get("codigo_municipio"):
                cmun = end.codigo_municipio if isinstance(end, Endereco) else end.get("codigo_municipio")
                if cmun:
                    data = dict(data)
                    data["codigo_municipio"] = str(cmun)
        return data

    @field_validator("codigo_municipio", mode="before")
    @classmethod
    def _norm_cmun(cls, v: Any) -> str:
        return _clean_digits(v or "3201308").zfill(7)[:7]

    @property
    def documento_limpo(self) -> str:
        return _clean_digits(self.cnpj or self.cpf or self.documento or "")

    @property
    def op_simp_nac(self) -> str:
        reg = (self.regime or "normal").lower()
        if reg in ("3", "simples", "simples_nacional", "me_epp"):
            return "3"
        if reg in ("2", "mei"):
            return "2"
        return "1"

    @property
    def regime_normalizado(self) -> str:
        op = self.op_simp_nac
        return "simples" if op == "3" else ("mei" if op == "2" else "normal")


class Tomador(BaseModel):
    """Schema do Tomador de Serviços (`<toma>`) da DPS v1.01."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    documento: Optional[str] = None
    razao_social: str = Field(default="Consumidor", validation_alias=AliasChoices("razao_social", "nome"))
    inscricao_municipal: Optional[str] = None
    nif: Optional[str] = None
    c_nao_nif: Optional[str] = None
    endereco: Optional[Endereco] = None
    email: Optional[str] = None
    fone: Optional[str] = Field(default=None, validation_alias=AliasChoices("fone", "telefone"))

    @model_validator(mode="before")
    @classmethod
    def _build_endereco_from_flat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            campos_end = ("logradouro", "numero", "complemento", "bairro", "codigo_municipio", "cep", "uf")
            tem_campo_solto = any(data.get(k) is not None for k in campos_end)
            if tem_campo_solto and not data.get("endereco"):
                data = dict(data)
                data["endereco"] = {k: data[k] for k in campos_end if data.get(k) is not None}
        return data

    @property
    def documento_limpo(self) -> str:
        return _clean_digits(self.documento or self.cnpj or self.cpf or "")


class Intermediario(BaseModel):
    """Schema do Intermediário do Serviço (`<interm>`) da DPS v1.01."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    documento: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    razao_social: str = "Intermediário"

    @property
    def documento_limpo(self) -> str:
        return _clean_digits(self.documento or self.cnpj or self.cpf or "")


class Servico(BaseModel):
    """Schema do Serviço Prestado (`<serv>`, `<valores>` e `<IBSCBS>`) da DPS v1.01."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    valor: float = Field(default=0.0, validation_alias=AliasChoices("valor", "valor_servicos"))
    cTribNac: str = Field(
        default="010101",
        validation_alias=AliasChoices("cTribNac", "codigo_lc116", "codigo_tributacao_nacional"),
    )
    descricao: str = Field(
        default="Prestação de serviços",
        validation_alias=AliasChoices("descricao", "discriminacao"),
    )
    codigo_municipio_prestacao: Optional[str] = None
    pais_prestacao: Optional[str] = None
    cTribMun: Optional[str] = None
    cNBS: Optional[str] = Field(default=None, validation_alias=AliasChoices("cNBS", "nbs"))
    cIntContrib: Optional[str] = None
    cClassTrib: str = "000001"
    cst: Optional[str] = None
    indop: str = Field(default="100301", validation_alias=AliasChoices("indop", "cIndOp"))
    aliquota_iss: Optional[float] = None
    iss_retido: bool = False
    reter_federais: bool = False
    valor_recebido: Optional[float] = None
    desconto_incondicionado: float = 0.0
    desconto_condicionado: float = 0.0
    idDocTec: Optional[str] = None
    docRef: Optional[str] = None
    xInfComp: Optional[str] = Field(default=None, validation_alias=AliasChoices("xInfComp", "infoCompl"))
    finNFSe: str = "0"
    indFinal: Optional[int | str] = None
    tpOper: Optional[int | str] = None
    refNFSe: Optional[List[str] | str] = None
    tpEnteGov: Optional[int | str] = None
    indDest: int | str = "0"
    cCredPres: Optional[str] = None
    tributacao_regular: Optional[Dict[str, Any]] = None
    substituicao: Optional[Substituicao] = None

    @field_validator("valor", "desconto_incondicionado", "desconto_condicionado", mode="before")
    @classmethod
    def _to_float(cls, v: Any) -> float:
        if v is None:
            return 0.0
        return float(v) if not isinstance(v, Decimal) else float(v)

    @field_validator("cTribNac", mode="before")
    @classmethod
    def _norm_ctribnac(cls, v: Any) -> str:
        return _clean_digits(v or "010101").zfill(6)[:6]

    @field_validator("codigo_municipio_prestacao", mode="before")
    @classmethod
    def _norm_cmun_prest(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return _clean_digits(v).zfill(7)[:7]


class DPS(BaseModel):
    """Schema raiz da Declaração de Prestação de Serviços (DPS v1.01)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    prestador: Prestador
    servico: Servico
    tomador: Optional[Tomador] = None
    intermediario: Optional[Intermediario] = None
    substituicao: Optional[Substituicao] = None
    tributacao: Optional[Dict[str, Any]] = None
    serie: str = Field(default="900", validation_alias=AliasChoices("serie", "serie_dps"))
    numero: int | str = Field(default=1, validation_alias=AliasChoices("numero", "numero_dps"))
    competencia: Optional[str | date | datetime] = Field(
        default=None, validation_alias=AliasChoices("competencia", "data_competencia")
    )
    data_emissao: Optional[str | datetime] = None
    regime_tributario: Optional[str] = None
    ambiente: str = "homologacao"
    incluir_ibscbs: bool = True
    versao_aplicativo: str = "NFSeManager-1.01"

    @model_validator(mode="after")
    def _sync_regime_prestador(self) -> DPS:
        if self.regime_tributario and self.prestador.regime == "normal":
            self.prestador.regime = self.regime_tributario
        return self

    @property
    def data_emissao_formatada(self) -> str:
        if isinstance(self.data_emissao, datetime):
            return self.data_emissao.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        if isinstance(self.data_emissao, str) and self.data_emissao.strip():
            return self.data_emissao.strip()
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")

    @property
    def competencia_formatada(self) -> str:
        if isinstance(self.competencia, (date, datetime)):
            return self.competencia.strftime("%Y-%m-%d")
        if isinstance(self.competencia, str) and self.competencia.strip():
            limpo = self.competencia.strip()
            return limpo[:10] if len(limpo) >= 10 else f"{limpo}-01"
        return self.data_emissao_formatada[:10]

    def obter_tributacao(self) -> Dict[str, Any]:
        """Retorna a tributação informada ou calcula automaticamente via `calcular_tributacao`."""
        if self.tributacao is not None:
            return self.tributacao

        from pynfse.adn.tax_calculator import calcular_tributacao

        return calcular_tributacao(
            valor_servicos=self.servico.valor,
            regime_prestador=self.prestador.regime_normalizado,
            cClassTrib=self.servico.cClassTrib,
            cst=self.servico.cst,
            cIndOp=self.servico.indop,
            cTribNac=self.servico.cTribNac,
            cNBS=self.servico.cNBS,
            data_competencia=self.competencia_formatada,
            desconto_incondicionado=self.servico.desconto_incondicionado,
            desconto_condicionado=self.servico.desconto_condicionado,
            aliquota_iss_informada=self.servico.aliquota_iss,
            iss_retido=self.servico.iss_retido,
            reter_federais=self.servico.reter_federais,
        )

    def to_xml(self) -> str:
        """Constrói o XML `<DPS versao="1.01">` diretamente a partir deste schema."""
        from pynfse.adn.dps_builder import build_dps_xml_from_schema

        return build_dps_xml_from_schema(self)

    def to_signed_xml(
        self,
        pfx_path: Optional[str] = None,
        pfx_password: Optional[str] = None,
        pfx_data: Optional[bytes] = None,
        signer: Optional[Any] = None,
    ) -> str:
        """Constrói o XML `<DPS versao="1.01">` e assina digitalmente a tag `infDPS` (XML-DSig)."""
        from pynfse.adn.adn_signer import DpsSigner

        xml_raw = self.to_xml()
        dps_signer = signer or DpsSigner(pfx_data=pfx_data, pfx_password=pfx_password, pfx_path=pfx_path)
        return dps_signer.sign_xml(xml_raw, tag_to_sign="infDPS")
