from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

PRODUTO_ORDEM = {
    "cdb": 0, "lci": 1, "lca": 1, "cri": 2, "cra": 2,
    "debenture": 3, "fii": 4, "fip": 5, "outro": 6,
}

RATING_NUM = {
    "AAA": 1.0, "AA+": 0.95, "AA": 0.90, "AA-": 0.85,
    "A+": 0.80, "A": 0.75, "A-": 0.70,
    "BBB+": 0.65, "BBB": 0.60, "BBB-": 0.55,
    "BB+": 0.45, "BB": 0.40, "BB-": 0.35,
    "B+": 0.25, "B": 0.20, "B-": 0.15,
    "CCC": 0.10, "CC": 0.05, "C": 0.02, "D": 0.0,
}

INDEXADOR_ONEHOT = {"cdi+": 0, "ipca+": 1, "pre": 2, "selic+": 3, "igpm+": 4}


def _numerar_rating(rating: Optional[str]) -> float:
    if not rating:
        return 0.5
    r = rating.upper().strip()
    for chave, val in RATING_NUM.items():
        if r == chave or r.startswith(chave):
            return val
    return 0.5


def _numerar_produto(produto: str) -> int:
    return PRODUTO_ORDEM.get(produto.lower(), 6)


def _numerar_indexador(indexador: str) -> int:
    return INDEXADOR_ONEHOT.get(indexador.lower().strip(), -1)


def extrair_features(ofertas: List[Dict[str, Any]]) -> np.ndarray:
    features = []
    for o in ofertas:
        try:
            spread = float(o.get("spread_bps", 0) or 0)
        except (TypeError, ValueError):
            spread = 0

        try:
            prazo = int(o.get("prazo_meses", 12) or 12)
        except (TypeError, ValueError):
            prazo = 12

        try:
            volume = float(o.get("volume_mm", 0) or 0)
        except (TypeError, ValueError):
            volume = 0

        rating = _numerar_rating(o.get("rating"))
        produto = _numerar_produto(o.get("produto", ""))
        idx = _numerar_indexador(o.get("indexador", ""))

        features.append([spread, prazo, volume, rating, produto, idx])

    if not features:
        return np.array([])

    return np.array(features, dtype=np.float64)


def clusterizar_ofertas(
    ofertas: List[Dict[str, Any]],
    eps: float = 0.5,
    min_samples: int = 2,
) -> List[Dict[str, Any]]:
    if len(ofertas) < min_samples:
        return [dict(o, cluster=-1) for o in ofertas]

    X = extrair_features(ofertas)
    if X.shape[0] < min_samples:
        return [dict(o, cluster=-1) for o in ofertas]

    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import DBSCAN

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    rotulos = clustering.fit_predict(X_scaled)

    resultado = []
    for i, oferta in enumerate(ofertas):
        resultado.append(dict(oferta, cluster=int(rotulos[i])))

    n_clusters = len(set(rotulos)) - (1 if -1 in rotulos else 0)
    n_ruido = sum(1 for r in rotulos if r == -1)
    logger.info(
        f"[Clustering] {len(ofertas)} ofertas → "
        f"{n_clusters} clusters, {n_ruido} outliers (eps={eps}, min_samples={min_samples})"
    )

    return resultado
