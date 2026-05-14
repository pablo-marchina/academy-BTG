from __future__ import annotations
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ..config import settings

logger = logging.getLogger(__name__)


async def enviar_webhook(
    url: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
) -> bool:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201, 202):
                logger.info(f"[Webhook] Enviado para {url}: {resp.status_code}")
                return True
            logger.warning(f"[Webhook] HTTP {resp.status_code} de {url}")
            return False
    except Exception as e:
        logger.error(f"[Webhook] Erro ao enviar para {url}: {e}")
        return False


async def notificar_oferta_webhook(
    oferta: Dict[str, Any],
    score: Optional[Dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    url = webhook_url or getattr(settings, "WEBHOOK_URL", "")
    if not url:
        return False

    payload = {
        "evento": "nova_oferta",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dados": {
            "codigo": oferta.get("codigo", ""),
            "emissor": oferta.get("emissor", ""),
            "produto": oferta.get("produto", ""),
            "taxa_raw": oferta.get("taxa_raw", ""),
            "indexador": oferta.get("indexador", ""),
            "rating": oferta.get("rating", ""),
            "vencimento": oferta.get("vencimento", ""),
            "coordenador": oferta.get("coordenador", ""),
        },
    }
    if score:
        payload["dados"]["score"] = score.get("score_total")
        payload["dados"]["spread_bps"] = score.get("spread_bps")

    return await enviar_webhook(url, payload)
