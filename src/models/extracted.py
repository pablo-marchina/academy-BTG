from __future__ import annotations
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field


class ProspectoExtraido(BaseModel):
    emissor: str = Field("", description="Nome do emissor / companhia")
    produto: str = Field("", description="Tipo do produto: debenture, cri, cra, cdb, lci, lca, fii, fip")
    indexador: str = Field("", description="Indexador: CDI, IPCA, PRE, SELIC, IGPM")
    taxa: Optional[float] = Field(None, description="Taxa da oferta em percentual (ex: 1.35 para CDI+1.35%)")
    taxa_raw: str = Field("", description="Taxa no formato original do prospecto")
    spread_bps: Optional[int] = Field(None, description="Spread em basis points sobre o indexador")
    vencimento: Optional[str] = Field(None, description="Data de vencimento (AAAA-MM-DD)")
    prazo_meses: Optional[int] = Field(None, description="Prazo em meses")
    rating: Optional[str] = Field(None, description="Rating do emissor/oferta (ex: AAA, AA+, A-)")
    rating_agencia: Optional[str] = Field(None, description="Agência de rating: S&P, Moody's, Fitch, etc.")
    garantias: str = Field("", description="Tipo de garantia: real, fidejussória, pessoal, flutuante, etc.")
    covenants: List[str] = Field(default_factory=list, description="Covenants financeiros e não-financeiros")
    coordenador: Optional[str] = Field(None, description="Coordenador líder da emissão")
    coordenadores: List[str] = Field(default_factory=list, description="Todos os coordenadores")
    isin: Optional[str] = Field(None, description="Código ISIN da oferta")
    volume_total: Optional[float] = Field(None, description="Volume total da emissão em reais")
    volume_info: str = Field("", description="Volume no formato original do prospecto")
    valor_unitario: Optional[float] = Field(None, description="Valor unitário de cada título")
    quantidade_ofertada: Optional[int] = Field(None, description="Quantidade de títulos ofertados")
    isento_ir: bool = Field(False, description="Se é isento de IR (LCA, LCI, CRA, CRI)")
    remuneracao: str = Field("", description="Descrição completa da remuneração")
    cronograma: str = Field("", description="Cronograma de eventos da oferta")
    data_emissao: Optional[str] = Field(None, description="Data de emissão")
    data_registro: Optional[str] = Field(None, description="Data de registro na CVM/ANBIMA")
    tipo_oferta: str = Field("", description="Tipo: pública, privada, esforços restritos, etc.")
    esforcos_restritos: bool = Field(False, description="Se é oferta com esforços restritos (Res. 160)")
    confidence_score: float = Field(0.0, description="Confiança da extração (0-1)")
    erros: List[str] = Field(default_factory=list, description="Problemas encontrados na extração")


class ExtracaoResult(BaseModel):
    documento_id: str = ""
    caminho_pdf: str = ""
    paginas_total: int = 0
    paginas_extraidas: int = 0
    texto_amostra: str = ""
    tamanho_texto: int = 0
    extraido: ProspectoExtraido = Field(default_factory=ProspectoExtraido)
    sucesso: bool = False
