"""
Coletor ANBIMA — OAuth2 corrigido.

Fix: Authorization: Basic base64(client_id:client_secret) + body JSON
     (não form-encoded como estava antes)
"""
from __future__ import annotations
import base64
from typing import List, Tuple, Optional
from datetime import date, datetime, timedelta
import logging
import httpx

from ..models.raw import RawOffer, RawDocument
from ..config import settings
from .base import BaseCollector

logger = logging.getLogger(__name__)

INDEXADOR_MAP = {
    "CDI": "cdi+", "% CDI": "cdi+", "DI": "cdi+", "DI+": "cdi+",
    "IPCA": "ipca+", "IPCA+": "ipca+",
    "PRÉ": "pre", "PRE": "pre", "PREFIXADO": "pre",
    "IGPM": "igpm+", "IGP-M": "igpm+", "IGP-M+": "igpm+",
    "SELIC": "selic+", "SELIC+": "selic+",
}

TOKEN_ENDPOINT = "https://api.anbima.com.br/oauth/access-token"


class ANBIMACollector(BaseCollector):
    name = "anbima"

    def __init__(self):
        if not settings.anbima_configurada:
            logger.warning(
                "[ANBIMA] Nenhuma credencial configurada. "
                "Cadastre em: https://developers.anbima.com.br/"
            )
        super().__init__()
        self.base          = settings.ANBIMA_BASE_URL
        self._ativa        = settings.anbima_configurada
        self._token        = settings.anbima_token_ativo
        self._token_expira: Optional[datetime] = None

    # ------------------------------------------------------------------ #
    # Coleta                                                               #
    # ------------------------------------------------------------------ #

    async def collect(
        self,
        data_inicio: Optional[date] = None,
        data_fim: Optional[date] = None,
        **kwargs,
    ) -> Tuple[List[RawOffer], List[RawDocument]]:
        if not self._ativa:
            return [], []

        if not data_fim:
            data_fim = date.today()

        ofertas: List[RawOffer] = []
        for tipo in ("Debentures", "CRI", "CRA", "FII", "FIP"):
            ofertas.extend(await self._fetch_titulos(tipo, data_fim))

        logger.info(f"[ANBIMA] {len(ofertas)} títulos coletados")
        return ofertas, []

    async def fetch_curvas(self, data: Optional[date] = None) -> dict:
        if not self._ativa:
            return {}
        if not data:
            data = date.today()

        curvas = {}
        for indice, chave in [("IPCA", "ntnb"), ("PRE", "di_pre")]:
            resp = await self._get_auth(
                f"{self.base}/feed/precos-indices/v1/curvas/ettj",
                {"Data": data.strftime("%Y-%m-%d"), "Indice": indice},
            )
            if resp:
                curvas[chave] = self._parse_curva(resp)
        return curvas

    # ------------------------------------------------------------------ #
    # OAuth2 — Basic auth + JSON body                                     #
    # ------------------------------------------------------------------ #

    async def _get_token_valido(self) -> str:
        """Retorna token válido, renovando se necessário."""
        if self._token and (
            self._token_expira is None
            or datetime.now() < self._token_expira
        ):
            return self._token

        if settings.ANBIMA_CLIENT_ID and settings.ANBIMA_CLIENT_SECRET:
            token, expira = await self._refresh_oauth2()
            if token:
                self._token = token
                self._token_expira = datetime.now() + timedelta(seconds=expira - 60)
                logger.info(f"[ANBIMA] Token renovado (expira em {expira}s)")
                return self._token

        return self._token

    async def _refresh_oauth2(self) -> tuple[str, int]:
        """
        Renovação de token.
        POST https://api.anbima.com.br/oauth/access-token
        Header: Authorization: Basic base64(client_id:client_secret)
        Body:   {"grant_type": "client_credentials"}  (JSON)
        """
        credenciais = base64.b64encode(
            f"{settings.ANBIMA_CLIENT_ID}:{settings.ANBIMA_CLIENT_SECRET}".encode()
        ).decode()

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    TOKEN_ENDPOINT,
                    json={"grant_type": "client_credentials"},
                    headers={
                        "Content-Type":  "application/json",
                        "Authorization": f"Basic {credenciais}",
                        },
                )
                if resp.status_code != 200:
                    logger.error(
                        f"[ANBIMA] Refresh falhou: HTTP {resp.status_code} — {resp.text[:200]}"
                    )
                    return "", 0
                body = resp.json()
                return body.get("access_token", ""), int(body.get("expires_in", 3600))
        except Exception as e:
            return "", 0

    # ------------------------------------------------------------------ #
    # HTTP autenticado                                                     #
    # ------------------------------------------------------------------ #

    async def _get_auth(self, url: str, params: dict = None) -> dict:
        """GET autenticado com retry automático em 401."""
        token = await self._get_token_valido()

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for tentativa in range(2):
                resp = await client.get(
                    url, params=params,
                    headers={"access-token": token, "Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 401 and tentativa == 0:
                    logger.info("[ANBIMA] 401 — forçando refresh de token")
                    self._token_expira = None
                    token = await self._get_token_valido()
                    continue
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"[ANBIMA] HTTP {resp.status_code} em {url}")
                return {}
        return {}

    # ------------------------------------------------------------------ #
    # Fetchers                                                             #
    # ------------------------------------------------------------------ #

    async def _fetch_titulos(self, tipo: str, data_ref: date) -> List[RawOffer]:
        produto = {"Debentures": "debenture", "CRI": "cri", "CRA": "cra", "FII": "fii", "FIP": "fip"}.get(tipo, tipo.lower())
        data = await self._get_auth(
            f"{self.base}/feed/precos-indices/v1/titulos-privados/pu-mtm",
            {"Data": data_ref.strftime("%Y-%m-%d"), "Tipo": tipo},
        )
        ofertas = []
        for item in data.get("Titulos", []):
            ofertas.append(RawOffer(
                codigo     = item.get("CodigoSELIC") or item.get("ISIN") or "",
                emissor    = item.get("NomeEmissor", ""),
                produto    = produto,
                indexador  = self._norm_idx(item.get("Indexador", "")),
                taxa_raw   = str(item.get("TaxaCompra", "")),
                vencimento = item.get("DataVencimento", ""),
                rating     = item.get("ClassificacaoRisco"),
                coordenador= None,
                volume_mm  = None,
                data_coleta= datetime.now(),
                fonte      = "anbima",
                url_origem = f"{self.base}/feed/precos-indices/v1/titulos-privados/pu-mtm",
                metadata   = item,
            ))
        return ofertas

    def _norm_idx(self, raw: str) -> str:
        upper = raw.upper().strip()
        for k, v in INDEXADOR_MAP.items():
            if k in upper:
                return v
        return raw.lower()

    def _parse_curva(self, data: dict) -> dict:
        curva = {}
        for item in data.get("Curva", data.get("curva", [])):
            try:
                curva[int(item.get("Vertice") or item.get("prazo"))] = \
                    float(item.get("Taxa") or item.get("taxa"))
            except (TypeError, ValueError):
                pass
        return curva
