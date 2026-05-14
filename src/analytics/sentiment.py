from __future__ import annotations
import logging
import re
from typing import Dict, Any, List
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FONTES_NOTICIAS = [
    "https://www.infomoney.com.br/mercados/",
    "https://www.valor.globo.com/mercados/",
]

PALAVRAS_CHAVE = [
    "emissao", "debenture", "cri", "cra", "cdb", "lci", "lca",
    "captacao", "oferta publica", "prospecto", "rating",
]


def coletar_noticias() -> List[Dict[str, Any]]:
    noticias = []
    for url in FONTES_NOTICIAS:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            textos = soup.get_text(separator=" ", strip=True).lower()

            for palavra in PALAVRAS_CHAVE:
                indices = [m.start() for m in re.finditer(palavra, textos)]
                for idx in indices[:2]:
                    ctx = textos[max(0, idx - 80): idx + 150]
                    noticias.append({
                        "fonte": url,
                        "palavra": palavra,
                        "contexto": ctx.strip(),
                        "data_coleta": datetime.now(),
                    })
        except Exception as e:
            logger.debug(f"[Sentimento] Erro em {url}: {e}")

    return noticias


def analisar_sentimento(texto: str) -> Dict[str, Any]:
    texto_lower = texto.lower()

    positivas = ["bom", "otimo", "crescimento", "recorde", "lucro", "elevacao", "upgrade", "positivo"]
    negativas = ["perda", "queda", "rebaixamento", "default", "inadimplencia", "negativo", "risco", "cancelamento"]

    score_pos = sum(1 for p in positivas if p in texto_lower)
    score_neg = sum(1 for n in negativas if n in texto_lower)
    total = score_pos + score_neg

    if total == 0:
        return {"sentimento": "neutro", "score": 0.5, "positivas": 0, "negativas": 0}

    score = score_pos / total if total > 0 else 0.5
    if score > 0.6:
        sentimento = "positivo"
    elif score < 0.4:
        sentimento = "negativo"
    else:
        sentimento = "neutro"

    return {"sentimento": sentimento, "score": round(score, 2), "positivas": score_pos, "negativas": score_neg}
