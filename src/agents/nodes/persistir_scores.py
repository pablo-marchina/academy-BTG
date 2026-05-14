from __future__ import annotations
import logging

from ..state import PipelineState
from ...db.engine import SessionLocal, init_db
from ...db.models import ScoreLog, Oferta

logger = logging.getLogger(__name__)


def node_persistir_scores(state: PipelineState) -> PipelineState:
    scores = state.get("analise", {}).get("scores", [])
    ofertas = state.get("ofertas_normalizadas", state.get("ofertas", []))
    if not scores or not ofertas:
        return state

    init_db()
    session = SessionLocal()
    try:
        for i, oferta in enumerate(ofertas):
            score = scores[i] if i < len(scores) else {}
            oferta_id = oferta.get("codigo") or oferta.get("id", "")
            if not oferta_id:
                continue

            log = ScoreLog(
                oferta_id=oferta_id,
                score_total=score.get("score_total", 0),
                score_confianca=score.get("score_confianca", 0),
                decomposicao=score.get("decomposicao"),
            )
            session.add(log)

            o = session.query(Oferta).filter(Oferta.id == oferta_id).first()
            if o:
                o.score_atratividade = score.get("score_total")
                o.score_confianca = score.get("score_confianca")
                o.taxa_cdi = oferta.get("taxa_cdi")
                o.taxa_ipca = oferta.get("taxa_ipca")
                o.taxa_pre = oferta.get("taxa_pre")
                o.spread_curva_bps = oferta.get("spread_bps")
                o.taxa_liquida = oferta.get("taxa_liquida")
                o.cluster_peers = oferta.get("cluster")

        session.commit()
        logger.info(f"[Persistir] {len(scores)} scores persistidos")
    except Exception as e:
        session.rollback()
        logger.error(f"[Persistir] Erro nos scores: {e}")
    finally:
        session.close()

    return state
