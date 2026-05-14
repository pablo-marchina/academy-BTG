from __future__ import annotations
import asyncio
import logging

from ..state import PipelineState

logger = logging.getLogger(__name__)


async def node_detectar_pre_publica(state: PipelineState) -> PipelineState:
    detectacoes = []
    try:
        from ...collectors.securitizadoras import SecuritizadoraCollector
        from ...collectors.ri_empresas import RICollector

        sec = SecuritizadoraCollector()
        ri = RICollector()

        resultados = await asyncio.gather(
            sec.collect(),
            ri.collect(),
            return_exceptions=True,
        )

        for resultado in resultados:
            if isinstance(resultado, Exception):
                logger.warning(f"[Detectar] Erro: {resultado}")
            elif isinstance(resultado, list):
                detectacoes.extend(resultado)

        logger.info(f"[Detectar] {len(detectacoes)} deteccoes pre-publica")
    except Exception as e:
        logger.warning(f"[Detectar] Erro geral: {e}")

    state["detectacoes_pre_publica"] = detectacoes
    return state
