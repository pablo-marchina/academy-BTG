from __future__ import annotations
import logging
import re
from typing import List, Dict, Any
from datetime import datetime

import httpx
from lxml import html

logger = logging.getLogger(__name__)

EMPRESAS_MONITORADAS = {
    "petrobras": "https://www.investidorpetrobras.com.br/",
    "vale": "https://www.vale.com/pt/investidores",
    "bradesco": "https://www.bradescori.com.br/",
    "itau": "https://www.itau.com.br/investidores/",
    "suzano": "https://www.suzano.com.br/investidores/",
    "gerdau": "https://www.gerdau.com.br/investidores",
}

PALAVRAS_EMISSAO = [
    "debenture", "debênture", "cri", "cra", "emissão", "emissao",
    "captação", "captacao", "oferta pública", "oferta publica",
    "prospecto", "distribuição", "distribuicao",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class RICollector:
    name = "ri_empresas"

    async def collect(self) -> List[Dict[str, Any]]:
        resultados = []
        async with httpx.AsyncClient(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            for empresa, url in EMPRESAS_MONITORADAS.items():
                try:
                    ofertas = await self._coletar_uma(client, empresa, url)
                    resultados.extend(ofertas)
                except Exception as e:
                    logger.debug(f"[RI/{empresa}] Erro: {e}")

        logger.info(f"[RI] {len(resultados)} mencoes de emissao encontradas")
        return resultados

    async def _coletar_uma(
        self, client: httpx.AsyncClient, empresa: str, url: str
    ) -> List[Dict[str, Any]]:
        ofertas = []
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            tree = html.fromstring(resp.text)
            textos = tree.xpath("//text()")
            conteudo = " ".join(t.strip() for t in textos if t.strip()).lower()

            for palavra in PALAVRAS_EMISSAO:
                indices = [m.start() for m in re.finditer(palavra, conteudo)]
                for idx in indices[:3]:
                    contexto = conteudo[max(0, idx - 100): idx + 200]
                    ofertas.append({
                        "fonte": f"ri_{empresa}",
                        "empresa": empresa,
                        "tipo_menção": palavra,
                        "contexto": contexto.strip(),
                        "data_coleta": datetime.now(),
                        "url": url,
                    })
                    break

        except Exception as e:
            logger.debug(f"[RI/{empresa}] Falha: {e}")

        return ofertas
