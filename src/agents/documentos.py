from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Any

from ..config import settings
from ..extractors.structured import extrair_prospecto
from ..models.extracted import ExtracaoResult

logger = logging.getLogger(__name__)


def node_extrair_documentos(state: Dict[str, Any]) -> Dict[str, Any]:
    documentos = state.get("documentos", [])
    if not documentos:
        logger.info("[Documentos] Nenhum documento para extrair")
        return state

    caminhos_pdf = []
    for d in documentos:
        caminho = d.get("caminho_local") or d.get("url", "")
        if caminho:
            caminhos_pdf.append(caminho)

    if not caminhos_pdf:
        logger.info("[Documentos] Nenhum PDF disponível")
        return state

    logger.info(f"[Documentos] Extraindo {len(caminhos_pdf)} PDFs...")
    extracoes = []
    for caminho in caminhos_pdf[:10]:
        try:
            resultado = extrair_prospecto(caminho, max_paginas=50)
            extracoes.append(resultado.model_dump())
        except Exception as e:
            logger.error(f"[Documentos] Erro extraindo {caminho}: {e}")

    state["extracoes"] = extracoes
    sucessos = sum(1 for e in extracoes if e.get("sucesso"))
    logger.info(f"[Documentos] {sucessos}/{len(extracoes)} extrações bem-sucedidas")
    return state
