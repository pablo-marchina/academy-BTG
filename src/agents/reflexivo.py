from __future__ import annotations
import logging
from typing import Dict, Any, Optional

from ..models.extracted import ProspectoExtraido
from ..config import settings

logger = logging.getLogger(__name__)


def re_extrair_se_necessario(
    extracao: Dict[str, Any],
    score_threshold: float = 0.5,
) -> Optional[Dict[str, Any]]:
    extraido = extracao.get("extraido", {})
    confidence = extraido.get("confidence_score", 1.0)

    if confidence >= score_threshold:
        return None

    logger.info(
        f"[Reflexivo] Re-extraindo {extracao.get('caminho_pdf', '')} "
        f"(confidence {confidence:.2f} < {score_threshold})"
    )
    return extracao


def avaliar_extracao(extracao: Dict[str, Any]) -> Dict[str, Any]:
    extraido = extracao.get("extraido", {})
    erros = extraido.get("erros", [])
    confidence = extraido.get("confidence_score", 0)

    campos_preenchidos = 0
    campos_possiveis = 0

    for campo in ["emissor", "produto", "indexador", "taxa", "vencimento"]:
        campos_possiveis += 1
        if extraido.get(campo):
            campos_preenchidos += 1

    for campo in ["rating", "coordenador", "isin", "garantias"]:
        campos_possiveis += 1
        if extraido.get(campo):
            campos_preenchidos += 1

    return {
        "documento_id": extracao.get("documento_id", ""),
        "confidence": confidence,
        "completeza": round(campos_preenchidos / max(campos_possiveis, 1), 2),
        "n_erros": len(erros),
        "erros": erros,
        "precisa_re_extracao": confidence < 0.5 or campos_preenchidos < 3,
        "n_campos_preenchidos": campos_preenchidos,
    }
