from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import joblib

from ..db.engine import SessionLocal
from ..db.models import Oferta

logger = logging.getLogger(__name__)

RATING_ORDEM = {
    "AAA": 10, "AA+": 9, "AA": 8, "AA-": 7,
    "A+": 6, "A": 5, "A-": 4,
    "BBB+": 3, "BBB": 2, "BBB-": 1, None: 0,
}

_modelo: Optional[object] = None
_features: List[str] = []
_score_medio_historico: float = 50.0
MODELO_PATH = Path("data/modelos/ridge.joblib")
FEATURES_PATH = Path("data/modelos/ridge_features.joblib")


def _rating_num(r: str) -> int:
    if not r:
        return 0
    r = r.upper().strip()
    for chave, val in RATING_ORDEM.items():
        if chave and (r == chave or r.startswith(chave)):
            return val
    return 0


def _carregar_treino() -> pd.DataFrame:
    session = SessionLocal()
    try:
        ofertas = session.query(Oferta).filter(
            Oferta.score_atratividade.isnot(None),
            Oferta.spread_curva_bps.isnot(None),
        ).all()
        data = []
        for o in ofertas:
            data.append({
                "spread_bps": o.spread_curva_bps or 0,
                "rating_num": _rating_num(o.rating),
                "volume_mm": o.volume_mm or 0,
                "score": o.score_atratividade or 50,
                "produto": o.produto or "",
            })
        return pd.DataFrame(data)
    finally:
        session.close()


def treinar_modelo() -> Dict[str, Any]:
    import pandas as pd
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_absolute_error, r2_score
    global _modelo, _features, _score_medio_historico

    df = _carregar_treino()
    if df.empty or len(df) < 20:
        logger.warning(f"[ScoreML] Dados insuficientes ({len(df)} amostras). Usando heuristica.")
        _modelo = None
        return {"status": "dados_insuficientes", "n_amostras": len(df)}

    produto_dummies = pd.get_dummies(df["produto"], prefix="prod")
    X = pd.concat([
        df[["spread_bps", "rating_num", "volume_mm"]],
        produto_dummies,
    ], axis=1)
    y = df["score"]
    _features = X.columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelos = {
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42),
    }

    melhor_modelo = None
    melhor_r2 = -999
    resultados = {}

    for nome, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        cv_scores = cross_val_score(modelo, X, y, cv=min(5, len(df) // 5), scoring="r2")
        resultados[nome] = {"r2": round(r2, 3), "mae": round(mae, 2), "cv_mean": round(cv_scores.mean(), 3)}

        if r2 > melhor_r2:
            melhor_r2 = r2
            melhor_modelo = modelo

    if melhor_r2 > 0:
        _modelo = melhor_modelo
        _score_medio_historico = float(y.mean())

    logger.info(f"[ScoreML] Modelo treinado: {len(df)} amostras, r2={melhor_r2:.3f}")
    return {
        "status": "ok",
        "n_amostras": len(df),
        "melhor_modelo": max(resultados, key=lambda k: resultados[k]["r2"]),
        "resultados": resultados,
    }


def prever_score(oferta: Dict[str, Any]) -> Dict[str, Any]:
    global _modelo, _features, _score_medio_historico

    if _modelo is None:
        r = treinar_modelo()
        if _modelo is None:
            return {"score_ml": None, "score_heuristica": _score_medio_historico, "erro": "modelo_nao_treinado"}

    spread = oferta.get("spread_bps", oferta.get("spread_curva_bps", 0)) or 0
    rating = _rating_num(oferta.get("rating", ""))
    volume = oferta.get("volume_mm", 0) or 0
    produto = oferta.get("produto", "")

    row = {"spread_bps": spread, "rating_num": rating, "volume_mm": volume}
    for feat in _features:
        if feat.startswith("prod_"):
            row[feat] = 1 if feat == f"prod_{produto}" else 0

    X_pred = pd.DataFrame([row])[_features]
    score_pred = float(_modelo.predict(X_pred)[0])
    score_pred = max(0, min(100, score_pred))

    return {
        "score_ml": round(score_pred, 1),
        "score_heuristica": None,
        "features_usadas": _features,
    }


def explicar_predicao(oferta: Dict[str, Any]) -> Dict[str, Any]:
    if _modelo is None:
        return {"erro": "modelo_nao_treinado"}

    spread = oferta.get("spread_bps", 0) or 0
    rating = _rating_num(oferta.get("rating", ""))
    volume = oferta.get("volume_mm", 0) or 0
    produto = oferta.get("produto", "")

    row = {"spread_bps": spread, "rating_num": rating, "volume_mm": volume}
    for feat in _features:
        if feat.startswith("prod_"):
            row[feat] = 1 if feat == f"prod_{produto}" else 0

    X_pred = pd.DataFrame([row])[_features]
    pred = _modelo.predict(X_pred)[0]

    if hasattr(_modelo, "coef_"):
        contribuicoes = {}
        for nome, coef in zip(_features, _modelo.coef_):
            contribuicoes[nome] = round(float(coef) * float(X_pred[nome].iloc[0]), 2)
        return {"predicao": round(float(pred), 1), "contribuicoes": contribuicoes, "modelo": type(_modelo).__name__}

    return {"predicao": round(float(pred), 1), "modelo": type(_modelo).__name__}


def _salvar_modelo_ridge(model):
    MODELO_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODELO_PATH)
    joblib.dump(_features, FEATURES_PATH)


def _carregar_modelo_ridge():
    global _modelo, _features
    if MODELO_PATH.exists():
        try:
            _modelo = joblib.load(MODELO_PATH)
            _features = joblib.load(FEATURES_PATH) if FEATURES_PATH.exists() else []
            logger.info(f"[Ridge] Modelo carregado de {MODELO_PATH}")
            return True
        except Exception as e:
            logger.warning(f"[Ridge] Erro ao carregar: {e}")
    return False
