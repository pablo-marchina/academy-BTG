from __future__ import annotations
import logging
from typing import Dict, Any, List

from .telegram import alertar_melhores_ofertas, formatar_alerta_oferta, enviar_mensagem
from .slack import enviar_alerta_slack

logger = logging.getLogger(__name__)


def alertar_todos_canais(
    ofertas: List[Dict[str, Any]],
    scores: List[Dict[str, Any]],
    macro: Dict[str, Any],
    canais: List[str] = None,
    limite: int = 5,
    threshold: float = 65.0,
) -> Dict[str, int]:
    if canais is None:
        canais = ["telegram"]

    resultados = {}
    for canal in canais:
        try:
            if canal == "telegram":
                n = alertar_melhores_ofertas(ofertas, scores, macro, limite, threshold)
                resultados[canal] = n
            elif canal == "slack":
                n = 0
                for i, oferta in enumerate(ofertas[:limite]):
                    s = scores[i]["score_total"] if i < len(scores) else 0
                    if s >= threshold and enviar_alerta_slack(oferta, s):
                        n += 1
                resultados[canal] = n
        except Exception as e:
            logger.error(f"[MultiChannel] Erro no canal {canal}: {e}")
            resultados[canal] = -1

    return resultados
