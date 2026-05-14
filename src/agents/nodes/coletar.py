from __future__ import annotations
import logging

from ..state import PipelineState
from ...collectors.pipeline import CollectionPipeline

logger = logging.getLogger(__name__)


async def node_coletar(state: PipelineState) -> PipelineState:
    pipeline = CollectionPipeline()
    ofertas, documentos, macro = await pipeline.run(
        data_inicio=state["data_inicio"],
        data_fim=state.get("data_fim"),
        baixar_pdfs=state.get("baixar_pdfs", True),
    )
    curvas = await pipeline.fetch_curvas()

    state["ofertas"] = [dict(o.__dict__) for o in ofertas]
    state["documentos"] = [dict(d.__dict__) for d in documentos]
    state["macro"] = macro
    state["curvas"] = curvas
    return state
