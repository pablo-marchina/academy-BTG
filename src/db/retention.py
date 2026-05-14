from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from ..db.engine import SessionLocal
from ..db.models import ScoreLog, MacroDiaria

logger = logging.getLogger(__name__)


def limpar_dados_antigos(dias_retencao: int = 90):
    session = SessionLocal()
    try:
        corte = datetime.now(timezone.utc) - timedelta(days=dias_retencao)

        n_score = session.query(ScoreLog).filter(ScoreLog.criado_em < corte).delete()
        n_macro = session.query(MacroDiaria).filter(MacroDiaria.criado_em < corte).delete()

        session.commit()
        if n_score or n_macro:
            logger.info(f"[Retention] Limpos: {n_score} score_logs, {n_macro} macro_diaria (>{dias_retencao}d)")
    except Exception as e:
        session.rollback()
        logger.error(f"[Retention] Erro: {e}")
    finally:
        session.close()
