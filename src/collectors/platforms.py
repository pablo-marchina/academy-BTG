"""
Coletor de plataformas corrigido.
Fix: ERR_HTTP2_PROTOCOL_ERROR — desabilita HTTP/2, usa domcontentloaded,
     adiciona stealth headers e retry.
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from datetime import datetime
import logging, json

from playwright.async_api import async_playwright, Page, Response

from ..models.raw import RawOffer, RawDocument

logger = logging.getLogger(__name__)

PLATAFORMAS = {
    "btg":    {"url": "https://www.btgpactual.com/investimentos/renda-fixa",    "nome": "BTG Pactual"},
    "xp":     {"url": "https://www.xpi.com.br/investimentos/renda-fixa/",       "nome": "XP Investimentos"},
    "genial": {"url": "https://www.genialinvestimentos.com.br/renda-fixa",       "nome": "Genial"},
}

PALAVRAS_RF = ["cdb","lci","lca","cri","cra","debênture","debenture","% cdi","ipca","prefixado","selic"]

# Flags Chrome que desabilitam HTTP/2 e recursos de detecção de automação
CHROME_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-http2",                      # desabilita HTTP/2
    "--ignore-certificate-errors",
    "--disable-web-security",
]


class PlatformCollector:
    name = "platforms"

    async def collect_all(self) -> Tuple[List[RawOffer], List[RawDocument]]:
        todas: List[RawOffer] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=CHROME_ARGS)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
                java_script_enabled=True,
                ignore_https_errors=True,
                extra_http_headers={
                    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )

            for pid, cfg in PLATAFORMAS.items():
                try:
                    page = await context.new_page()
                    # Remove navigator.webdriver
                    await page.add_init_script(
                        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
                    )
                    ofertas = await self._coletar(page, pid, cfg)
                    todas.extend(ofertas)
                    logger.info(f"[{cfg['nome']}] {len(ofertas)} ofertas coletadas")
                    await page.close()
                except Exception as e:
                    logger.error(f"[{cfg['nome']}] Erro: {e}")

            await browser.close()

        return todas, []

    async def _coletar(self, page: Page, pid: str, cfg: dict) -> List[RawOffer]:
        api_data: list = []

        async def capturar(response: Response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and response.status == 200:
                try:
                    body = await response.json()
                    if self._parece_produtos(body):
                        api_data.append(body)
                except Exception:
                    pass

        page.on("response", capturar)

        # Tenta carregar — usa domcontentloaded (mais tolerante que networkidle)
        carregou = False
        for wait in ("domcontentloaded", "load"):
            try:
                await page.goto(cfg["url"], wait_until=wait, timeout=20_000)
                await page.wait_for_timeout(2_000)
                carregou = True
                break
            except Exception as e:
                logger.debug(f"[{cfg['nome']}] {wait} falhou: {e}")

        if not carregou:
            logger.warning(f"[{cfg['nome']}] Página não carregou — pulando")
            return []

        # 1. Tenta API interceptada
        ofertas = []
        for body in api_data:
            ofertas.extend(self._parse_api(body, cfg["nome"], pid))

        # 2. Fallback HTML
        if not ofertas:
            ofertas = await self._parse_html(page, cfg["nome"], pid)

        return ofertas

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def _parse_api(self, data: dict, nome: str, fonte: str) -> List[RawOffer]:
        items = (data.get("data") or data.get("products") or
                 data.get("items") or data.get("results") or
                 (data if isinstance(data, list) else []))
        ofertas = []
        for item in (items if isinstance(items, list) else []):
            if not isinstance(item, dict):
                continue
            o = self._dict_to_offer(item, nome, fonte)
            if o:
                ofertas.append(o)
        return ofertas

    def _dict_to_offer(self, item: dict, coordenador: str, fonte: str) -> Optional[RawOffer]:
        texto = json.dumps(item).lower()
        produto = self._prod(texto)
        if produto not in {"cdb","lci","lca","cri","cra","debenture","fii"}:
            return None
        return RawOffer(
            codigo     = item.get("isin") or item.get("code") or item.get("codigo") or "",
            emissor    = item.get("issuer") or item.get("emissor") or item.get("bank") or "",
            produto    = produto,
            indexador  = self._idx(texto),
            taxa_raw   = str(item.get("rate") or item.get("taxa") or item.get("yield") or ""),
            vencimento = str(item.get("maturity") or item.get("vencimento") or ""),
            rating     = item.get("rating"),
            coordenador= coordenador,
            volume_mm  = None,
            data_coleta= datetime.now(),
            fonte      = f"{fonte}_api",
            url_origem = PLATAFORMAS.get(fonte, {}).get("url"),
            metadata   = item,
        )

    async def _parse_html(self, page: Page, coordenador: str, fonte: str) -> List[RawOffer]:
        import re
        ofertas = []
        seletores = [
            "[data-testid='product-card']","[class*='product-card']",
            "[class*='offer-card']","[class*='card-produto']","article",
        ]
        for sel in seletores:
            try:
                items = await page.query_selector_all(sel)
                if not items:
                    continue
                for el in items:
                    texto = await el.inner_text()
                    if not any(p in texto.lower() for p in PALAVRAS_RF):
                        continue
                    m = re.search(r"(\d+[,.]?\d*\s*%|\d+[,.]?\d*\s*[×x]\s*CDI)", texto)
                    taxa = m.group(0) if m else ""
                    ofertas.append(RawOffer(
                        codigo="", emissor="", produto=self._prod(texto.lower()),
                        indexador=self._idx(texto.lower()), taxa_raw=taxa,
                        vencimento="", rating=None, coordenador=coordenador,
                        volume_mm=None, data_coleta=datetime.now(),
                        fonte=f"{fonte}_html", url_origem=page.url,
                        metadata={"texto": texto[:400]},
                    ))
                if ofertas:
                    break
            except Exception:
                continue
        return ofertas

    def _parece_produtos(self, data) -> bool:
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return any(k in data[0] for k in ["isin","taxa","rate","yield","produto"])
        if isinstance(data, dict):
            for k in ["data","products","items","results"]:
                v = data.get(k)
                if isinstance(v, list) and v:
                    return True
        return False

    def _prod(self, t: str) -> str:
        if "cdb" in t:                              return "cdb"
        if "lci" in t:                              return "lci"
        if "lca" in t:                              return "lca"
        if "cri" in t:                              return "cri"
        if "cra" in t:                              return "cra"
        if "debênture" in t or "debenture" in t:   return "debenture"
        if "fii" in t:                              return "fii"
        return "outro"

    def _idx(self, t: str) -> str:
        t = t.upper()
        if "IPCA" in t:                          return "ipca+"
        if "CDI" in t or " DI" in t:            return "cdi+"
        if "SELIC" in t:                         return "selic+"
        if "IGP" in t:                           return "igpm+"
        if "%" in t:                             return "pre"
        return ""
