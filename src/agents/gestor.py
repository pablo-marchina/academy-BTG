from __future__ import annotations
import asyncio
import inspect
import logging
import time
from datetime import date, timedelta
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END

from .state import PipelineState
from .nodes import (
    node_coletar,
    node_extrair_documentos,
    node_persistir,
    node_analisar,
    node_persistir_scores,
    node_graphrag_index,
    node_detectar_pre_publica,
    node_alertar,
    node_sintetizar,
)
from ..config import settings
from ..db.engine import init_db

logger = logging.getLogger(__name__)


def _registrar_erro(name: str):
    try:
        from ..api.metrics import registrar_erro as _re
        _re(name)
    except Exception:
        pass


def _wrap_node(name: str, func):
    async def wrapped(state: PipelineState) -> PipelineState:
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(state)
            else:
                result = func(state)
            return result
        except Exception as e:
            _registrar_erro(name)
            state.setdefault("erros", []).append(f"{name}: {e}")
            logger.error(f"[{name}] Erro: {e}")
            return state
    return wrapped


def build_gestor() -> StateGraph:
    workflow = StateGraph(PipelineState)

    workflow.add_node("coletar", _wrap_node("coletar", node_coletar))
    workflow.add_node("extrair", _wrap_node("extrair", node_extrair_documentos))
    workflow.add_node("persistir", _wrap_node("persistir", node_persistir))
    workflow.add_node("analisar", _wrap_node("analisar", node_analisar))
    workflow.add_node("persistir_scores", _wrap_node("persistir_scores", node_persistir_scores))
    workflow.add_node("graphrag", _wrap_node("graphrag", node_graphrag_index))
    workflow.add_node("detectar", _wrap_node("detectar", node_detectar_pre_publica))
    workflow.add_node("alertar", _wrap_node("alertar", node_alertar))
    workflow.add_node("sintetizar", _wrap_node("sintetizar", node_sintetizar))

    workflow.set_entry_point("coletar")
    workflow.add_edge("coletar", "extrair")
    workflow.add_edge("extrair", "persistir")
    workflow.add_edge("persistir", "analisar")
    workflow.add_edge("analisar", "persistir_scores")
    workflow.add_edge("persistir_scores", "graphrag")
    workflow.add_edge("graphrag", "detectar")
    workflow.add_edge("detectar", "alertar")
    workflow.add_edge("alertar", "sintetizar")
    workflow.add_edge("sintetizar", END)

    return workflow.compile()


async def run_pipeline(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    baixar_pdfs: bool = True,
) -> Dict[str, Any]:
    if not data_inicio:
        data_inicio = date.today() - timedelta(days=settings.DATE_LOOKBACK_DAYS)
    if not data_fim:
        data_fim = date.today()

    gestor = build_gestor()

    state: PipelineState = {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "baixar_pdfs": baixar_pdfs,
        "erros": [],
        "ofertas": [],
        "documentos": [],
        "extracoes": [],
        "ofertas_normalizadas": [],
        "macro": {},
        "curvas": {},
        "analise": {},
        "detectacoes_pre_publica": [],
        "graphrag_indexado": False,
        "mensagem_usuario": "",
        "mensagem_resposta": "",
    }

    inicio = time.time()
    result = await gestor.ainvoke(state)
    duracao = time.time() - inicio

    ofertas = result.get("ofertas", [])
    documentos = result.get("documentos", [])
    erros = result.get("erros", [])

    try:
        from ..api.metrics import registrar_coleta, registrar_duracao, registrar_ultima_coleta
        for o in ofertas:
            registrar_coleta(o.get("fonte", "desconhecida"))
        registrar_duracao(duracao)
        registrar_ultima_coleta()
    except Exception:
        pass

    try:
        from ..db.engine import SessionLocal, init_db
        from ..db.models import PipelineRun
        init_db()
        session = SessionLocal()
        session.add(PipelineRun(
            data_inicio=data_inicio,
            data_fim=data_fim,
            duracao_segundos=round(duracao, 1),
            n_ofertas=len(ofertas),
            n_documentos=len(documentos),
            n_erros=len(erros),
            erros="; ".join(erros[:10]) if erros else None,
            baixou_pdfs=baixar_pdfs,
            status="concluido" if not erros else "com_erros",
        ))
        session.commit()
        session.close()
    except Exception:
        pass

    try:
        from ..notifiers.webhook import notificar_oferta_webhook
        scores = result.get("analise", {}).get("scores", [])
        for i, o in enumerate(ofertas[:3]):
            s = scores[i] if i < len(scores) else None
            import asyncio
            asyncio.ensure_future(notificar_oferta_webhook(o, s))
    except Exception:
        pass

    logger.info(f"[Pipeline] Concluido em {duracao:.0f}s, {len(ofertas)} ofertas, {len(erros)} erros")

    return result


if __name__ == "__main__":
    async def main():
        result = await run_pipeline()
        print(result.get("analise", {}).get("resumo", ""))

    asyncio.run(main())
