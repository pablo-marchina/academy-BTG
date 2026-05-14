from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any, List

import joblib

from ..db.engine import SessionLocal
from ..db.models import Oferta

logger = logging.getLogger(__name__)

_modelo_xgb = None
_features_xgb: List[str] = []
_score_medio = 50.0
_metricas: Dict[str, Any] = {}
MODELO_PATH = Path("data/modelos/xgboost.joblib")
FEATURES_PATH = Path("data/modelos/xgboost_features.joblib")


def _rating_num(r: str) -> int:
    if not r:
        return 0
    ordem = {"AAA": 10, "AA+": 9, "AA": 8, "AA-": 7, "A+": 6, "A": 5, "A-": 4, "BBB+": 3, "BBB": 2, "BBB-": 1}
    for chave, val in ordem.items():
        if r.upper().strip().startswith(chave):
            return val
    return 0


def _carregar_dados():
    import pandas as pd
    session = SessionLocal()
    try:
        ofertas = session.query(Oferta).filter(
            Oferta.score_atratividade.isnot(None),
            Oferta.spread_curva_bps.isnot(None),
        ).all()
        data = [{
            "spread_bps": o.spread_curva_bps or 0,
            "rating_num": _rating_num(o.rating),
            "volume_mm": o.volume_mm or 0,
            "score": o.score_atratividade or 50,
            "produto": o.produto or "",
        } for o in ofertas]
        return pd.DataFrame(data)
    finally:
        session.close()


def _salvar_modelo(model):
    MODELO_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODELO_PATH)
    joblib.dump(_features_xgb, FEATURES_PATH)


def _carregar_modelo():
    global _modelo_xgb, _features_xgb
    if MODELO_PATH.exists():
        try:
            _modelo_xgb = joblib.load(MODELO_PATH)
            _features_xgb = joblib.load(FEATURES_PATH) if FEATURES_PATH.exists() else []
            logger.info(f"[XGB] Modelo carregado de {MODELO_PATH}")
            return True
        except Exception as e:
            logger.warning(f"[XGB] Erro ao carregar: {e}")
    return False


def treinar_xgboost() -> Dict[str, Any]:
    import pandas as pd
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    global _modelo_xgb, _features_xgb, _score_medio, _metricas

    df = _carregar_dados()
    if df.empty or len(df) < 20:
        logger.warning(f"[XGB] Dados insuficientes ({len(df)})")
        _modelo_xgb = None
        return {"status": "dados_insuficientes", "n": len(df)}

    _score_medio = float(df["score"].mean())
    produto_dummies = pd.get_dummies(df["produto"], prefix="prod")
    X = pd.concat([df[["spread_bps", "rating_num", "volume_mm"]], produto_dummies], axis=1)
    y = df["score"]
    _features_xgb = X.columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, eval_metric="mae",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    imp = dict(zip(_features_xgb, model.feature_importances_))

    _modelo_xgb = model
    _metricas = {
        "r2": round(r2, 3),
        "mae": round(mae, 2),
        "n_amostras": len(df),
        "feature_importance": {k: round(v, 3) for k, v in sorted(imp.items(), key=lambda x: -x[1])[:10]},
    }
    _salvar_modelo(model)

    logger.info(f"[XGB] Treinado: r2={r2:.3f}, mae={mae:.2f}, {len(df)} amostras")
    return {"status": "ok", **_metricas}


def prever_xgboost(oferta: Dict[str, Any]) -> Dict[str, Any]:
    import pandas as pd
    global _modelo_xgb, _features_xgb, _score_medio

    if _modelo_xgb is None:
        if not _carregar_modelo():
            r = treinar_xgboost()
            if _modelo_xgb is None:
                return {"score_xgb": None, "fallback": round(_score_medio, 1), "erro": "nao_treinado"}

    row = {
        "spread_bps": oferta.get("spread_bps", 0) or 0,
        "rating_num": _rating_num(oferta.get("rating", "")),
        "volume_mm": oferta.get("volume_mm", 0) or 0,
    }
    for feat in _features_xgb:
        if feat.startswith("prod_"):
            row[feat] = 1 if feat == f"prod_{oferta.get('produto', '')}" else 0

    X_pred = pd.DataFrame([row])[_features_xgb]
    score = float(_modelo_xgb.predict(X_pred)[0])
    return {"score_xgb": round(max(0, min(100, score)), 1), "fallback": None}


def explicar_xgboost(oferta: Dict[str, Any]) -> Dict[str, Any]:
    base = prever_xgboost(oferta)
    if base.get("score_xgb") is None:
        return base
    base["feature_importance"] = _metricas.get("feature_importance", {})
    base["modelo"] = "XGBoost"
    return base
