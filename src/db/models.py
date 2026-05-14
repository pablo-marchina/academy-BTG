from __future__ import annotations
import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Integer, Date, Boolean


def _utcnow():
    return datetime.now(timezone.utc)

from .engine import Base


class Oferta(Base):
    __tablename__ = "ofertas"

    id = Column(String, primary_key=True)
    codigo = Column(String, index=True)
    fonte = Column(String, index=True)
    produto = Column(String, index=True)
    emissor = Column(String, index=True)
    indexador = Column(String)
    taxa_raw = Column(String)
    vencimento = Column(String)
    rating = Column(String, nullable=True)
    coordenador = Column(String, nullable=True)
    volume_mm = Column(Float, nullable=True)
    data_coleta = Column(DateTime, default=_utcnow)
    url_origem = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    # Normalizados
    taxa_cdi = Column(Float, nullable=True)
    taxa_ipca = Column(Float, nullable=True)
    taxa_pre = Column(Float, nullable=True)
    spread_curva_bps = Column(Float, nullable=True)
    taxa_liquida = Column(Float, nullable=True)

    # Score
    score_atratividade = Column(Float, nullable=True)
    score_confianca = Column(Float, nullable=True)
    cluster_peers = Column(Integer, nullable=True)

    criado_em = Column(DateTime, default=_utcnow)
    atualizado_em = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(String, primary_key=True)
    oferta_id = Column(String, index=True, nullable=True)
    nome_arquivo = Column(String, nullable=True)
    url = Column(Text)
    caminho_local = Column(Text, nullable=True)
    tipo = Column(String, default="documento_emissao")
    emissor = Column(String, nullable=True)
    codigo_oferta = Column(String, nullable=True)
    data_documento = Column(String, nullable=True)
    fonte = Column(String, index=True)
    metadata_json = Column(JSON, nullable=True)

    criado_em = Column(DateTime, default=_utcnow)


class MacroDiaria(Base):
    __tablename__ = "macro_diaria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, index=True)
    selic_atual = Column(Float, nullable=True)
    selic_proxima = Column(Float, nullable=True)
    ipca_12m = Column(Float, nullable=True)
    ipca_proximo_12m = Column(Float, nullable=True)
    igpm_12m = Column(Float, nullable=True)
    ptax_dolar = Column(Float, nullable=True)
    regime_mercado = Column(String, nullable=True)
    curva_di = Column(JSON, nullable=True)
    criado_em = Column(DateTime, default=_utcnow)


class ScoreLog(Base):
    __tablename__ = "score_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    oferta_id = Column(String, index=True)
    score_total = Column(Float)
    score_confianca = Column(Float)
    premio_curva = Column(Float, nullable=True)
    rating_pts = Column(Float, nullable=True)
    garantia_pts = Column(Float, nullable=True)
    liquidez_pts = Column(Float, nullable=True)
    timing_pts = Column(Float, nullable=True)
    origem_pts = Column(Float, nullable=True)
    complexidade_pts = Column(Float, nullable=True)
    decomposicao = Column(JSON, nullable=True)
    criado_em = Column(DateTime, default=_utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_inicio = Column(Date)
    data_fim = Column(Date)
    duracao_segundos = Column(Float)
    n_ofertas = Column(Integer, default=0)
    n_documentos = Column(Integer, default=0)
    n_erros = Column(Integer, default=0)
    erros = Column(Text, nullable=True)
    baixou_pdfs = Column(Boolean, default=False)
    status = Column(String, default="concluido")
    criado_em = Column(DateTime, default=_utcnow)
