from __future__ import annotations
import logging
from typing import Dict, Any, Optional
from datetime import date

from .anbima import ANBIMACollector

logger = logging.getLogger(__name__)


def comparar_com_benchmark(
    oferta: Dict[str, Any],
    curvas: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not curvas:
        return {"benchmark": None, "diferenca_bps": None}

    produto = oferta.get("produto", "").lower()
    indexador = oferta.get("indexador", "").upper().strip()
    prazo_meses = 12

    venc = oferta.get("vencimento", "")
    if venc and len(str(venc)) >= 10:
        try:
            from datetime import datetime
            dv = datetime.strptime(str(venc)[:10], "%Y-%m-%d")
            prazo_meses = max((dv.date() - date.today()).days // 30, 1)
        except ValueError:
            pass

    taxa_referencia = None
    nome_curva = None

    if "CDI" in indexador and "di_pre" in curvas:
        curva = curvas["di_pre"]
        nome_curva = "DI x PRE"
        if isinstance(curva, dict):
            closest = min(curva.keys(), key=lambda k: abs(k - prazo_meses))
            taxa_referencia = curva[closest]

    elif "IPCA" in indexador and "ntnb" in curvas:
        curva = curvas["ntnb"]
        nome_curva = "NTN-B"
        if isinstance(curva, dict):
            closest = min(curva.keys(), key=lambda k: abs(k - prazo_meses))
            taxa_referencia = curva[closest]

    if taxa_referencia is None or "selic" in produto:
        return {"benchmark": None, "diferenca_bps": None, "curva": nome_curva, "taxa_curva": None}

    try:
        taxa_oferta = float(oferta.get("taxa_raw", "0").replace(",", ".").replace("%", ""))
    except (ValueError, AttributeError):
        return {"benchmark": None, "diferenca_bps": None}

    premio = round((taxa_oferta - taxa_referencia) * 100, 1)

    return {
        "benchmark": nome_curva,
        "taxa_curva": round(taxa_referencia, 4),
        "taxa_oferta": taxa_oferta,
        "premio_bps": premio,
        "prazo_meses": prazo_meses,
        "avaliacao": "acima_curva" if premio > 0 else ("abaixo_curva" if premio < 0 else "na_curva"),
    }


async def buscar_curvas_atualizadas() -> Dict[str, Any]:
    try:
        collector = ANBIMACollector()
        async with collector:
            curvas = await collector.fetch_curvas()
        logger.info(f"[Benchmark] Curvas atualizadas: {list(curvas.keys())}")
        return curvas
    except Exception as e:
        logger.error(f"[Benchmark] Erro ao buscar curvas: {e}")
        return {}
