from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Depends
from typing import Optional, List
from datetime import date

from ..db.engine import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
from ..db.models import Oferta, MacroDiaria
from ..analytics.matching import PerfilInvestidor, calcular_match
from ..analytics.score_xgb import prever_xgboost, treinar_xgboost, explicar_xgboost
from ..analytics.anomalies import detectar_anomalia, listar_anomalias, treinar_deteccao_anomalias
from ..analytics.score_ml import treinar_modelo
from .metrics import export_metrics
from .middleware import RateLimitMiddleware
from .auth import verificar_api_key

app = FastAPI(
    title="BTG Intelligence API",
    version="0.5.0",
    description="API para consulta de ofertas primarias, matching por perfil, ML score e deteccao de anomalias",
    contact={"name": "BTG Intelligence", "url": "https://btgintelligence.com"},
    license_info={"name": "Proprietario"},
    lifespan=lifespan,
)
app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.4.0"}


@app.get("/metrics")
def metrics():
    return export_metrics()


@app.get("/ofertas")
def listar_ofertas(
    produto: Optional[str] = None,
    emissor: Optional[str] = None,
    indexador: Optional[str] = None,
    score_min: float = 0,
    limite: int = 50,
    _=Depends(verificar_api_key),
):
    session = SessionLocal()
    try:
        q = session.query(Oferta).filter(Oferta.score_atratividade.isnot(None))
        if produto:
            q = q.filter(Oferta.produto == produto.lower())
        if emissor:
            q = q.filter(Oferta.emissor.ilike(f"%{emissor}%"))
        if indexador:
            q = q.filter(Oferta.indexador.ilike(f"%{indexador}%"))
        if score_min > 0:
            q = q.filter(Oferta.score_atratividade >= score_min)
        ofertas = q.order_by(Oferta.score_atratividade.desc()).limit(limite).all()
        return [
            {
                "codigo": o.codigo,
                "emissor": o.emissor,
                "produto": o.produto,
                "indexador": o.indexador,
                "taxa_raw": o.taxa_raw,
                "rating": o.rating,
                "coordenador": o.coordenador,
                "score": o.score_atratividade,
                "spread_bps": o.spread_curva_bps,
                "volume_mm": o.volume_mm,
                "vencimento": o.vencimento,
            }
            for o in ofertas
        ]
    finally:
        session.close()


@app.get("/ofertas/{codigo}")
def detalhe_oferta(codigo: str, _=Depends(verificar_api_key)):
    session = SessionLocal()
    try:
        o = session.query(Oferta).filter(Oferta.codigo == codigo).first()
        if not o:
            raise HTTPException(404, "Oferta nao encontrada")
        return {
            "codigo": o.codigo,
            "emissor": o.emissor,
            "produto": o.produto,
            "indexador": o.indexador,
            "taxa_raw": o.taxa_raw,
            "taxa_cdi": o.taxa_cdi,
            "taxa_ipca": o.taxa_ipca,
            "taxa_pre": o.taxa_pre,
            "taxa_liquida": o.taxa_liquida,
            "rating": o.rating,
            "coordenador": o.coordenador,
            "score": o.score_atratividade,
            "score_confianca": o.score_confianca,
            "spread_bps": o.spread_curva_bps,
            "volume_mm": o.volume_mm,
            "vencimento": o.vencimento,
            "fonte": o.fonte,
            "cluster": o.cluster_peers,
        }
    finally:
        session.close()


@app.get("/macro")
def macro(_=Depends(verificar_api_key)):
    session = SessionLocal()
    try:
        m = session.query(MacroDiaria).order_by(MacroDiaria.data.desc()).first()
        if not m:
            raise HTTPException(404, "Dados macro nao disponiveis")
        return {
            "data": m.data.isoformat() if m.data else None,
            "selic_atual": m.selic_atual,
            "ipca_12m": m.ipca_12m,
            "igpm_12m": m.igpm_12m,
            "regime_mercado": m.regime_mercado,
            "curva_di": m.curva_di,
        }
    finally:
        session.close()


@app.post("/match")
def match_ofertas(
    perfil: str = Query("moderado", description="conservador, moderado, arrojado"),
    produto: Optional[str] = None,
    score_min: float = 0,
    limite: int = 10,
    _=Depends(verificar_api_key),
):
    perfis = {
        "conservador": PerfilInvestidor.conservador,
        "moderado": PerfilInvestidor.moderado,
        "arrojado": PerfilInvestidor.arrojado,
    }
    if perfil not in perfis:
        raise HTTPException(400, f"Perfil invalido: {perfil}. Use: conservador, moderado, arrojado")

    session = SessionLocal()
    try:
        q = session.query(Oferta).filter(Oferta.score_atratividade.isnot(None))
        if produto:
            q = q.filter(Oferta.produto == produto.lower())
        if score_min > 0:
            q = q.filter(Oferta.score_atratividade >= score_min)
        ofertas = q.order_by(Oferta.score_atratividade.desc()).limit(limite * 2).all()
    finally:
        session.close()

    p = perfis[perfil]()
    matches = []
    for o in ofertas:
        oferta_dict = {
            "produto": o.produto,
            "indexador": o.indexador,
            "taxa_raw": o.taxa_raw,
            "rating": o.rating,
            "vencimento": o.vencimento or "",
            "codigo": o.codigo,
        }
        m = calcular_match(oferta_dict, p)
        matches.append({
            "codigo": o.codigo,
            "emissor": o.emissor,
            "produto": o.produto,
            "score_oferta": o.score_atratividade,
            "match_score": m["match_score"],
            "match_label": m["match_label"],
            "rejeicoes": m["rejeicoes"],
            "avisos": m["avisos"],
        })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:limite]


@app.get("/stats")
def stats(_=Depends(verificar_api_key)):
    session = SessionLocal()
    try:
        total = session.query(Oferta).count()
        com_score = session.query(Oferta).filter(Oferta.score_atratividade.isnot(None)).count()
        media = session.query(Oferta).filter(Oferta.score_atratividade.isnot(None)).with_entities(
            Oferta.score_atratividade
        ).all()
        media_score = sum(m[0] for m in media) / len(media) if media else 0
        return {"total_ofertas": total, "com_score": com_score, "score_medio": round(media_score, 1)}
    finally:
        session.close()


@app.post("/ml/treinar")
def ml_treinar(_=Depends(verificar_api_key)):
    r_xgb = treinar_xgboost()
    r_ml = treinar_modelo()
    r_anom = treinar_deteccao_anomalias()
    return {"xgboost": r_xgb, "score_ml": r_ml, "anomalias": r_anom}


@app.post("/ml/prever/{codigo}")
def ml_prever(codigo: str, _=Depends(verificar_api_key)):
    session = SessionLocal()
    try:
        o = session.query(Oferta).filter(Oferta.codigo == codigo).first()
        if not o:
            raise HTTPException(404, "Oferta nao encontrada")
        oferta_dict = {
            "spread_bps": o.spread_curva_bps,
            "rating": o.rating,
            "volume_mm": o.volume_mm,
            "produto": o.produto,
            "score_atratividade": o.score_atratividade,
        }
        xgb = prever_xgboost(oferta_dict)
        anom = detectar_anomalia({**oferta_dict, "score_total": o.score_atratividade})
        return {"codigo": codigo, "xgboost": xgb, "anomalia": anom, "score_atual": o.score_atratividade}
    finally:
        session.close()


@app.get("/pipeline/historico")
def pipeline_historico(limite: int = 20, _=Depends(verificar_api_key)):
    from ..db.models import PipelineRun
    session = SessionLocal()
    try:
        runs = session.query(PipelineRun).order_by(PipelineRun.criado_em.desc()).limit(limite).all()
        return [
            {
                "id": r.id,
                "data_inicio": r.data_inicio.isoformat() if r.data_inicio else None,
                "duracao_segundos": r.duracao_segundos,
                "n_ofertas": r.n_ofertas,
                "n_erros": r.n_erros,
                "status": r.status,
                "criado_em": r.criado_em.isoformat() if r.criado_em else None,
            }
            for r in runs
        ]
    finally:
        session.close()


@app.get("/ml/anomalias")
def ml_anomalias(limite: int = 20, _=Depends(verificar_api_key)):
    return {"anomalias": listar_anomalias(limite)}


@app.get("/ml/explicar/{codigo}")
def ml_explicar(codigo: str, _=Depends(verificar_api_key)):
    session = SessionLocal()
    try:
        o = session.query(Oferta).filter(Oferta.codigo == codigo).first()
        if not o:
            raise HTTPException(404)
        oferta_dict = {
            "spread_bps": o.spread_curva_bps,
            "rating": o.rating,
            "volume_mm": o.volume_mm,
            "produto": o.produto,
        }
        return explicar_xgboost(oferta_dict)
    finally:
        session.close()
