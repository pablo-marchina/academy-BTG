from __future__ import annotations
import logging
from typing import Dict, Any, List

from ..db.engine import SessionLocal
from ..db.models import Oferta

logger = logging.getLogger(__name__)

_modelo_if = None


def _carregar_features():
    import numpy as np
    session = SessionLocal()
    try:
        ofertas = session.query(Oferta).filter(
            Oferta.score_atratividade.isnot(None),
            Oferta.spread_curva_bps.isnot(None),
        ).all()
        X = []
        for o in ofertas:
            X.append([
                o.spread_curva_bps or 0,
                o.score_atratividade or 50,
                o.volume_mm or 0,
            ])
        return np.array(X, dtype=np.float64)
    finally:
        session.close()


def treinar_deteccao_anomalias(contaminacao: float = 0.05) -> Dict[str, Any]:
    from sklearn.ensemble import IsolationForest
    global _modelo_if
    X = _carregar_features()
    if len(X) < 10:
        logger.warning(f"[Anomalias] Dados insuficientes ({len(X)})")
        _modelo_if = None
        return {"status": "dados_insuficientes", "n": len(X)}

    modelo = IsolationForest(contamination=contaminacao, random_state=42, n_estimators=100)
    modelo.fit(X)
    _modelo_if = modelo

    rotulos = modelo.predict(X)
    n_anomalias = sum(1 for r in rotulos if r == -1)
    logger.info(f"[Anomalias] Treinado: {len(X)} amostras, {n_anomalias} anomalias ({contaminacao:.0%})")
    return {"status": "ok", "n_amostras": len(X), "n_anomalias": n_anomalias}


def detectar_anomalia(oferta: Dict[str, Any]) -> Dict[str, Any]:
    import numpy as np
    global _modelo_if
    if _modelo_if is None:
        r = treinar_deteccao_anomalias()
        if _modelo_if is None:
            return {"anomalia": None, "erro": "nao_treinado"}

    X = np.array([[
        oferta.get("spread_bps", 0) or 0,
        oferta.get("score_total", oferta.get("score_atratividade", 50)) or 50,
        oferta.get("volume_mm", 0) or 0,
    ]], dtype=np.float64)

    pred = int(_modelo_if.predict(X)[0])
    score = float(_modelo_if.score_samples(X)[0])

    return {
        "anomalia": pred == -1,
        "score_anomalia": round(score, 4),
        "severidade": "alta" if pred == -1 else "normal",
    }


def listar_anomalias(limite: int = 20) -> List[Dict[str, Any]]:
    import numpy as np
    global _modelo_if
    if _modelo_if is None:
        treinar_deteccao_anomalias()

    session = SessionLocal()
    try:
        ofertas = session.query(Oferta).filter(
            Oferta.score_atratividade.isnot(None),
            Oferta.spread_curva_bps.isnot(None),
        ).all()
    finally:
        session.close()

    X = np.array([[
        o.spread_curva_bps or 0, o.score_atratividade or 50, o.volume_mm or 0
    ] for o in ofertas], dtype=np.float64)

    if _modelo_if and len(X) > 0:
        preds = _modelo_if.predict(X)
        scores = _modelo_if.score_samples(X)
        anomalos = [(i, o, scores[i]) for i, (o, p) in enumerate(zip(ofertas, preds)) if p == -1]
        anomalos.sort(key=lambda x: x[2])
        return [{
            "codigo": o.codigo,
            "emissor": o.emissor,
            "produto": o.produto,
            "score_oferta": o.score_atratividade,
            "spread": o.spread_curva_bps,
            "score_anomalia": round(s, 4),
        } for i, o, s in anomalos[:limite]]

    return []
