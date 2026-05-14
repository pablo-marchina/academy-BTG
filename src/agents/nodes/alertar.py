from __future__ import annotations
import logging

from ..state import PipelineState
from ...notifiers.telegram import alertar_melhores_ofertas
from ...config import settings

logger = logging.getLogger(__name__)

SCORE_ALERTA_THRESHOLD = 65.0


def node_alertar(state: PipelineState) -> PipelineState:
    scores = state.get("analise", {}).get("scores", [])
    ofertas = state.get("ofertas", [])
    macro = state.get("macro", {})

    if scores and ofertas:
        enviadas = alertar_melhores_ofertas(
            ofertas, scores, macro,
            limite=5, threshold=SCORE_ALERTA_THRESHOLD,
        )
        state["analise"]["alertas_enviados"] = enviadas
        if enviadas:
            logger.info(f"[Alertas] {enviadas} alertas enviados via Telegram")

    return state
