from __future__ import annotations
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import date, datetime

import httpx
from lxml import html

from ..models.raw import RawOffer, RawDocument

logger = logging.getLogger(__name__)

SECURITIZADORAS = {
    "true": {
        "url": "https://www.true.com.br/emissoes/",
        "nome": "True Securitizadora",
        "seletor": "//div[contains(@class, 'emissao') or contains(@class, 'card')]",
    },
    "opea": {
        "url": "https://www.opea.com.br/emissoes/",
        "nome": "Opea Securitizadora",
        "seletor": "//div[contains(@class, 'card')]",
    },
    "habitasec": {
        "url": "https://habitasec.com.br/emissoes/",
        "nome": "Habitasec",
        "seletor": "//div[contains(@class, 'produto')]",
    },
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class SecuritizadoraCollector:
    name = "securitizadoras"

    async def collect(self) -> List[Dict[str, Any]]:
        resultados = []
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for pid, cfg in SECURITIZADORAS.items():
                try:
                    ofertas = await self._coletar_uma(client, pid, cfg)
                    resultados.extend(ofertas)
                    logger.info(f"[{cfg['nome']}] {len(ofertas)} potenciais ofertas")
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
                logger.debug(f"[{cfg['nome']}] HTTP {resp.status_code}")
                return []

            tree = html.fromstring(resp.text)
            cards = tree.xpath(cfg["seletor"]) or tree.xpath("//article") or tree.xpath("//section[contains(@class, 'card')]")

            for card in cards[:10]:
                texto = card.text_content().strip()
                if not texto or len(texto) < 30:
                    continue

                ofertas.append({
                    "fonte": f"securitizadora_{pid}",
                    "emissor": self._extrair_emissor(texto),
                    "produto": self._detectar_produto(texto),
                    "indexador": self._detectar_indexador(texto),
                    "taxa_raw": self._extrair_taxa(texto),
                    "data_coleta": datetime.now(),
                    "metadata": {"texto": texto[:500], "url": cfg["url"]},
                })

        except Exception as e:
            logger.warning(f"[{cfg['nome']}] Falha: {e}")

        return ofertas

    def _extrair_emissor(self, texto: str) -> str:
        linhas = [l.strip() for l in texto.split("\n") if l.strip()]
        for linha in linhas[:5]:
            if len(linha) > 5 and len(linha) < 100:
                return linha
        return ""

    def _detectar_produto(self, texto: str) -> str:
        t = texto.lower()
        if "cri" in t: return "cri"
        if "cra" in t: return "cra"
        if "debenture" in t or "debênture" in t: return "debenture"
        if "fii" in t: return "fii"
        if "fip" in t: return "fip"
        return "outro"

    def _detectar_indexador(self, texto: str) -> str:
        t = texto.upper()
        if "IPCA" in t: return "ipca+"
        if "CDI" in t: return "cdi+"
        if "PRE" in t or "PREFIXADO" in t: return "pre"
        if "SELIC" in t: return "selic+"
        if "IGP" in t: return "igpm+"
        return ""

    def _extrair_taxa(self, texto: str) -> str:
        m = re.search(r"(\d+[.,]\d*\s*%[^)]*)", texto)
        if m:
            return m.group(1).strip()
        m = re.search(r"(\d+[.,]\d*\s*[×xX]\s*CDI)", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""
