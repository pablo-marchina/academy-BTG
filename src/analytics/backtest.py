from __future__ import annotations
import logging
from typing import Dict, Any, List

import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np

from ..db.engine import SessionLocal
from ..db.models import Oferta, ScoreLog

logger = logging.getLogger(__name__)


def _carregar_historico() -> pd.DataFrame:
    session = SessionLocal()
    try:
        ofertas = session.query(Oferta).filter(
            Oferta.score_atratividade.isnot(None),
            Oferta.spread_curva_bps.isnot(None),
        ).all()
        data = []
        for o in ofertas:
            data.append({
                "codigo": o.codigo,
                "produto": o.produto,
                "rating": o.rating or "BBB",
                "prazo_dias": 365,
                "volume_mm": o.volume_mm or 0,
                "spread_bps": o.spread_curva_bps or 0,
                "score": o.score_atratividade or 0,
                "taxa_cdi": o.taxa_cdi or 0,
                "taxa_ipca": o.taxa_ipca or 0,
            })
        return pd.DataFrame(data)
    finally:
        session.close()


def backtest_score(
    periodo_dias: int = 365,
    threshold_alto: float = 70.0,
    threshold_baixo: float = 40.0,
) -> Dict[str, Any]:
    df = _carregar_historico()
    if df.empty:
        return {"erro": "Sem dados historicos para backtest"}

    total = len(df)
    acima_threshold = len(df[df["score"] >= threshold_alto])
    abaixo_threshold = len(df[df["score"] <= threshold_baixo])
    medio = df["score"].mean()

    return {
        "total_ofertas": total,
        "score_medio": round(medio, 1),
        "score_max": round(df["score"].max(), 1),
        "score_min": round(df["score"].min(), 1),
        "acima_threshold": acima_threshold,
        "abaixo_threshold": abaixo_threshold,
        "pct_alto_score": round(acima_threshold / total * 100, 1) if total else 0,
        "pct_baixo_score": round(abaixo_threshold / total * 100, 1) if total else 0,
        "std_dev": round(df["score"].std(), 1),
    }


def calcular_fair_value_spread(oferta: Dict[str, Any]) -> Dict[str, Any]:
    df = _carregar_historico()
    if df.empty or len(df) < 5:
        return {"fair_value_spread": None, "erro": "Dados insuficientes"}

    df_modelo = df.dropna(subset=["spread_bps", "score"])
    if len(df_modelo) < 5:
        return {"fair_value_spread": None, "erro": "Amostra insuficiente"}

    produto = oferta.get("produto", "").lower()
    df_prod = df_modelo[df_modelo["produto"] == produto] if produto in df_modelo["produto"].values else df_modelo

    if len(df_prod) < 3:
        df_prod = df_modelo

    try:
        X = df_prod[["score"]].values
        y = df_prod["spread_bps"].values

        model = LinearRegression()
        model.fit(X, y)

        score_val = oferta.get("score_atratividade", oferta.get("score_total", 50))
        spread_pred = model.predict([[score_val]])[0]

        spread_real = oferta.get("spread_bps", oferta.get("spread_curva_bps"))

        diferenca = None
        if spread_real is not None:
            diferenca = round(spread_real - spread_pred, 1)

        return {
            "fair_value_spread": round(spread_pred, 1),
            "spread_real": round(spread_real, 1) if spread_real else None,
            "diferenca_bps": diferenca,
            "ativo_ou_caro": "ativo" if diferenca and diferenca > 0 else ("caro" if diferenca and diferenca < 0 else "justo"),
            "confianca_modelo": round(model.score(X, y), 2),
            "n_amostra": len(df_prod),
        }
    except Exception as e:
        return {"fair_value_spread": None, "erro": str(e)}
