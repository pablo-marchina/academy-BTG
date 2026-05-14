from __future__ import annotations
import logging

from ..state import PipelineState
from ...analytics.normalizacao import normalizar_oferta
from ...analytics.score import calcular_score
from ...analytics.clustering import clusterizar_ofertas

logger = logging.getLogger(__name__)


def node_analisar(state: PipelineState) -> PipelineState:
    ofertas = state.get("ofertas", [])
    macro = state.get("macro", {})
    curvas = state.get("curvas", {})

    if not ofertas:
        logger.info("[Analista] Nenhuma oferta para analisar")
        return state

    normalizadas = []
    scores = []
    for o in ofertas:
        norm = normalizar_oferta(o, curvas)
        normalizadas.append({**o, **norm})
        score = calcular_score(o, norm, macro)
        scores.append(score)

    clusterizadas = clusterizar_ofertas(normalizadas, eps=0.6, min_samples=2)

    state["ofertas_normalizadas"] = clusterizadas
    state["analise"]["scores"] = scores
    state["analise"]["clusters"] = [
        {"cluster": c.get("cluster"), "count": sum(1 for x in clusterizadas if x.get("cluster") == c.get("cluster"))}
        for c in clusterizadas[:10]
    ]

    logger.info(f"[Analista] {len(scores)} ofertas analisadas")
    return state
