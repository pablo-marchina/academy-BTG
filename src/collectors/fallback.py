from __future__ import annotations
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

FALHAS_SEQUENCIAIS: Dict[str, int] = {}
FALHA_LIMIAR = 3
ULTIMA_DESATIVACAO: Dict[str, Optional[datetime]] = {}


def registrar_falha(fonte: str) -> bool:
    global FALHAS_SEQUENCIAIS
    FALHAS_SEQUENCIAIS[fonte] = FALHAS_SEQUENCIAIS.get(fonte, 0) + 1
    count = FALHAS_SEQUENCIAIS[fonte]

    if count >= FALHA_LIMIAR:
        logger.warning(f"[Fallback] {fonte}: {count} falhas consecutivas — desativando temporariamente")
        ULTIMA_DESATIVACAO[fonte] = datetime.now()
        return True
    return False


def registrar_sucesso(fonte: str):
    if fonte in FALHAS_SEQUENCIAIS:
        del FALHAS_SEQUENCIAIS[fonte]


def verificar_disponivel(fonte: str, tempo_reativacao_minutos: int = 30) -> bool:
    if fonte not in ULTIMA_DESATIVACAO:
        return True
    desativado_em = ULTIMA_DESATIVACAO[fonte]
    if desativado_em is None:
        return True
    from datetime import timedelta
    if datetime.now() - desativado_em > timedelta(minutes=tempo_reativacao_minutos):
        logger.info(f"[Fallback] Reativando {fonte} apos {tempo_reativacao_minutos}min")
        ULTIMA_DESATIVACAO[fonte] = None
        FALHAS_SEQUENCIAIS.pop(fonte, None)
        return True
    return False


def status_todos() -> Dict[str, Any]:
    return {
        "falhas_sequenciais": dict(FALHAS_SEQUENCIAIS),
        "desativados": {k: v.isoformat() if v else None for k, v in ULTIMA_DESATIVACAO.items()},
    }
