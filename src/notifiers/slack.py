from __future__ import annotations
import logging
from typing import Dict, Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import settings

logger = logging.getLogger(__name__)


def enviar_slack(mensagem: str, channel: str = "#btg-inteligencia") -> bool:
    token = settings.GROQ_API_KEY and settings.GROQ_API_KEY[:5]
    if not token:
        logger.warning("[Slack] Nenhum token Slack configurado")
        return False

    try:
        client = WebClient(token=getattr(settings, "SLACK_BOT_TOKEN", ""))
        resp = client.chat_postMessage(channel=channel, text=mensagem)
        logger.info(f"[Slack] Mensagem enviada para {channel}")
        return True
    except SlackApiError as e:
        logger.error(f"[Slack] Erro: {e}")
        return False
    except Exception:
        logger.debug("[Slack] Slack nao configurado")
        return False


def enviar_alerta_slack(oferta: Dict[str, Any], score: float) -> bool:
    msg = (
        f"*BTG Intelligence - Alerta*\n"
        f"*{oferta.get('produto', '?').upper()}* - {oferta.get('emissor', '?')}\n"
        f"Taxa: {oferta.get('taxa_raw', '?')} ({oferta.get('indexador', '?')})\n"
        f"Score: {score:.1f}\n"
        f"Rating: {oferta.get('rating', 'N/D')}"
    )
    return enviar_slack(msg)
