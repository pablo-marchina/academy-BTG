from __future__ import annotations
import logging
import re
from typing import List, Dict, Any
from datetime import datetime

import httpx
from lxml import html

logger = logging.getLogger(__name__)

RATING_SITES = {
    "liberum": {
        "url": "https://liberumratings.com.br/emissoes/",
        "nome": "Liberum Ratings",
    },
    "austin": {
        "url": "https://www.austinrating.com.br/rating/emissoes",
        "nome": "Austin Rating",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class RatingAgencyCollector:
    name = "rating_agencies"

    async def collect(self) -> List[Dict[str, Any]]:
        resultados = []
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for pid, cfg in RATING_SITES.items():
                try:
                    ofertas = await self._coletar_uma(client, pid, cfg)
                    resultados.extend(ofertas)
                    logger.info(f"[{cfg['nome']}] {len(ofertas)} ratings encontrados")
                except Exception as e:
                    logger.warning(f"[{cfg['nome']}] Erro: {e}")

        return resultados

    async def _coletar_uma(
        self, client: httpx.AsyncClient, pid: str, cfg: dict
    ) -> List[Dict[str, Any]]:
        ofertas = []
        try:
            resp = await client.get(cfg["url"])
            if resp.status_code != 200:
                return []

            tree = html.fromstring(resp.text)
            textos = tree.xpath("//text()")
            conteudo = " ".join(t.strip() for t in textos if t.strip())

            ratings_encontrados = re.findall(
                r"(AAA|AA\+?|AA\-?|A\+?|A\-?|BBB\+?|BBB\-?|BB\+?|BB\-?|B\+?|B\-?|CCC|CC|C|D)"
                r"(?:\s*[\(/]\s*([^\)]+))?",
                conteudo,
            )

            for rating, emissor in ratings_encontrados[:20]:
                ofertas.append({
                    "fonte": f"rating_{pid}",
                    "rating": rating,
                    "emissor": emissor.strip() if emissor else "",
                    "agencia": cfg["nome"],
                    "data_coleta": datetime.now(),
                    "metadata": {"url": cfg["url"]},
                })

        except Exception as e:
            logger.warning(f"[{cfg['nome']}] Falha: {e}")

        return ofertas
