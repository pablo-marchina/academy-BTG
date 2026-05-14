from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def enviar_mensagem(texto: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("[Telegram] Token ou chat_id não configurados")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        resp = httpx.post(url, json={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        if resp.status_code == 200:
            logger.info("[Telegram] Mensagem enviada com sucesso")
            return True
        else:
            logger.error(f"[Telegram] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[Telegram] Erro ao enviar: {e}")
        return False


def formatar_alerta_oferta(
    oferta: Dict[str, Any],
    score: Optional[Dict[str, Any]] = None,
    macro: Optional[Dict[str, Any]] = None,
) -> str:
    produto = oferta.get("produto", "?").upper()
    emissor = oferta.get("emissor", "?")
    taxa = oferta.get("taxa_raw", "?")
    indexador = oferta.get("indexador", "?")
    vencimento = oferta.get("vencimento", "?")
    coordenador = oferta.get("coordenador", "?")
    rating = oferta.get("rating", "N/D")

    linhas = [
        f"<b>🚀 {produto} — {emissor}</b>",
        f"📊 {taxa} ({indexador})",
        f"📅 Venc: {vencimento}",
        f"🏦 Coord: {coordenador}",
        f"⭐ Rating: {rating}",
    ]

    if score:
        linhas.append(f"🎯 Score: <b>{score.get('score_total', 0):.1f}</b> (conf: {score.get('score_confianca', 0):.0%})")
        decomp = score.get("decomposicao", {})
        if decomp:
            partes = [f"{k}: {v}" for k, v in sorted(decomp.items(), key=lambda x: -x[1])[:4]]
            linhas.append("📈 " + " | ".join(partes))

    if macro:
        linhas.append(f"📌 SELIC: {macro.get('selic_atual', '?')}% | IPCA: {macro.get('ipca_12m', '?')}%")

    return "\n".join(linhas)


def alertar_melhores_ofertas(
    ofertas: List[Dict[str, Any]],
    scores: List[Dict[str, Any]],
    macro: Optional[Dict[str, Any]] = None,
    limite: int = 5,
    threshold: float = 65.0,
) -> int:
    if not ofertas or not scores:
        return 0

    ofertas_com_score = []
    for i, o in enumerate(ofertas):
        s = scores[i] if i < len(scores) else {}
        ofertas_com_score.append((o, s))

    ofertas_com_score.sort(key=lambda x: x[1].get("score_total", 0), reverse=True)

    enviadas = 0
    for oferta, score in ofertas_com_score[:limite]:
        if score.get("score_total", 0) >= threshold:
            msg = formatar_alerta_oferta(oferta, score, macro)
            if enviar_mensagem(msg):
                enviadas += 1

    logger.info(f"[Telegram] {enviadas} alertas enviados (threshold={threshold})")
    return enviadas


def alertar_resumo(
    total_ofertas: int,
    media_score: float,
    melhores: List[str],
    erros: List[str],
) -> bool:
    linhas = [
        "Resumo Diario - BTG Intelligence",
        f"Ofertas analisadas: {total_ofertas}",
        f"Score medio: {media_score:.1f}",
    ]
    if melhores:
        linhas.append(f"Melhores: {', '.join(melhores[:3])}")
    if erros:
        linhas.append(f"Erros: {len(erros)}")

    return enviar_mensagem("\n".join(linhas))


EMISSORES_WATCHLIST: List[str] = []


def adicionar_watchlist(emissor: str):
    if emissor and emissor not in EMISSORES_WATCHLIST:
        EMISSORES_WATCHLIST.append(emissor)
        logger.info(f"[Watchlist] Adicionado: {emissor}")


def remover_watchlist(emissor: str):
    if emissor in EMISSORES_WATCHLIST:
        EMISSORES_WATCHLIST.remove(emissor)
        logger.info(f"[Watchlist] Removido: {emissor}")


def verificar_watchlist(ofertas: List[Dict[str, Any]]) -> List[str]:
    alertas = []
    for o in ofertas:
        emissor = o.get("emissor", "")
        if any(w.upper() in emissor.upper() for w in EMISSORES_WATCHLIST):
            msg = (
                f"Watchlist: {emissor} - {o.get('produto', '?')} "
                f"taxa {o.get('taxa_raw', '?')}"
            )
            alertas.append(msg)
            if enviar_mensagem(f"<b>ALERTA WATCHLIST</b>\n{msg}"):
                logger.info(f"[Watchlist] Alerta enviado: {emissor}")
    return alertas
