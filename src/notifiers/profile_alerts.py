from __future__ import annotations
import logging
from typing import Dict, Any, List
from datetime import datetime

from ..config import settings
from ..db.engine import SessionLocal
from ..db.models import Oferta

logger = logging.getLogger(__name__)


class AlertaPerfil:
    def __init__(self, nome: str = "", threshold_score: float = 65.0, watchlist: List[str] = None, canais: List[str] = None):
        self.nome = nome
        self.threshold_score = threshold_score
        self.watchlist = watchlist or []
        self.canais = canais or ["telegram"]


_perfis_alerta: List[AlertaPerfil] = [
    AlertaPerfil(nome="default", threshold_score=65.0, canais=["telegram"]),
]


def adicionar_perfil_alerta(perfil: AlertaPerfil):
    _perfis_alerta.append(perfil)
    logger.info(f"[PerfilAlerta] Perfil '{perfil.nome}' adicionado")


def processar_alertas_por_perfil(ofertas: List[Dict[str, Any]], scores: List[Dict[str, Any]], macro: Dict[str, Any]):
    from .telegram import alertar_melhores_ofertas, enviar_mensagem, verificar_watchlist

    for perfil in _perfis_alerta:
        ofertas_filtradas = []
        scores_filtrados = []

        for i, o in enumerate(ofertas):
            s = scores[i] if i < len(scores) else {}
            if s.get("score_total", 0) >= perfil.threshold_score:
                ofertas_filtradas.append(o)
                scores_filtrados.append(s)

        if "telegram" in perfil.canais:
            alertar_melhores_ofertas(
                ofertas_filtradas, scores_filtrados, macro,
                limite=5, threshold=perfil.threshold_score,
            )

            if perfil.watchlist:
                verificar_watchlist(ofertas_filtradas)

        from .slack import enviar_alerta_slack
        if "slack" in perfil.canais:
            for o, s in zip(ofertas_filtradas[:3], scores_filtrados[:3]):
                enviar_alerta_slack(o, s.get("score_total", 0))
