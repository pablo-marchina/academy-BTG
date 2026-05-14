from __future__ import annotations
import logging

from ..state import PipelineState

logger = logging.getLogger(__name__)


def node_graphrag_index(state: PipelineState) -> PipelineState:
    ofertas = state.get("ofertas_normalizadas", state.get("ofertas", []))
    if not ofertas:
        return state

    try:
        from ...vectorstore.qdrant_store import indexar_ofertas_batch
        from ...vectorstore.graphrag import get_graphrag

        n = indexar_ofertas_batch(ofertas)
        logger.info(f"[GraphRAG] {n} ofertas indexadas no Qdrant")

        g = get_graphrag()
        g.carregar()
        state["graphrag_indexado"] = True
        logger.info(f"[GraphRAG] Grafo carregado: {g.resumo_mercado()['total_ofertas']} ofertas")
    except Exception as e:
        logger.error(f"[GraphRAG] Erro: {e}")
        state.setdefault("erros", []).append(str(e))

    return state
