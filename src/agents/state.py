from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional
from datetime import date


class PipelineState(TypedDict):
    data_inicio: date
    data_fim: date
    baixar_pdfs: bool
    erros: List[str]

    ofertas: List[Dict[str, Any]]
    documentos: List[Dict[str, Any]]
    extracoes: List[Dict[str, Any]]
    ofertas_normalizadas: List[Dict[str, Any]]
    macro: Dict[str, Any]
    curvas: Dict[str, Any]

    analise: Dict[str, Any]

    detectacoes_pre_publica: List[Dict[str, Any]]
    graphrag_indexado: bool

    mensagem_usuario: str
    mensagem_resposta: str
