"""
Coletor BCB corrigido.
Fix Focus: remove filtro de data que causava 400 Bad Request no OData.
Fix SGS: usa sempre 365 dias para séries mensais.
"""
from __future__ import annotations
from typing import Optional, Dict
from datetime import date, timedelta
import logging
import httpx
import pandas as pd
from bcb import sgs

logger = logging.getLogger(__name__)

SGS_SERIES = {
    "selic_meta":   432,
    "di_overnight": 12,
    "ipca_mensal":  433,
    "ptax_dolar":   1,
    "igpm_mensal":  189,
}

FOCUS_BASE = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas"
    "/versao/v1/odata"
)


class BCBCollector:
    name = "bcb"
    LOOKBACK_DIAS = 365

    async def collect_macro(
        self,
        data_inicio: Optional[date] = None,
        data_fim: Optional[date] = None,
    ) -> Dict:
        data_fim_macro    = date.today()
        data_inicio_macro = data_fim_macro - timedelta(days=self.LOOKBACK_DIAS)

        series = self._fetch_series(data_inicio_macro, data_fim_macro)

        resultado = {
            "series":       series,
            "selic_atual":  self._ultimo(series, "selic_meta"),
            "ipca_12m":     self._acum12m(series, "ipca_mensal"),
            "igpm_12m":     self._acum12m(series, "igpm_mensal"),
            "ptax_dolar":   self._ultimo(series, "ptax_dolar"),
        }

        focus = await self._fetch_focus()
        resultado["focus"]            = focus
        resultado["selic_proxima"]    = self._selic_proxima(focus)
        resultado["ipca_proximo_12m"] = self._ipca_focus(focus)
        resultado["curva_di"]         = self._curva_di(resultado["selic_atual"], focus)
        resultado["regime_mercado"]   = self._regime(series)

        logger.info(
            f"[BCB] SELIC: {resultado['selic_atual']:.2f}% | "
            f"IPCA 12m: {resultado['ipca_12m']:.2f}% | "
            f"Regime: {resultado['regime_mercado']}"
        )
        return resultado

    # ------------------------------------------------------------------ #
    # SGS                                                                  #
    # ------------------------------------------------------------------ #

    def _fetch_series(self, inicio: date, fim: date) -> Dict[str, pd.Series]:
        series: Dict[str, pd.Series] = {}
        try:
            df = sgs.get(
                codes=SGS_SERIES,
                start=inicio.strftime("%Y-%m-%d"),
                end=fim.strftime("%Y-%m-%d"),
            )
            for nome in SGS_SERIES:
                if nome in df.columns:
                    s = df[nome].dropna()
                    if not s.empty:
                        series[nome] = s
        except Exception as e:
            logger.warning(f"[BCB] Falha bloco SGS: {e} — tentando individualmente")

        for nome, codigo in SGS_SERIES.items():
            if nome in series:
                continue
            try:
                df = sgs.get(
                    {nome: codigo},
                    start=inicio.strftime("%Y-%m-%d"),
                    end=fim.strftime("%Y-%m-%d"),
                )
                if not df.empty:
                    series[nome] = df.iloc[:, 0].dropna()
            except Exception as e:
                logger.debug(f"[BCB] Série {nome} indisponível: {e}")

        return series

    # ------------------------------------------------------------------ #
    # Focus — OData sem filtro de data (fix do 400 Bad Request)          #
    # ------------------------------------------------------------------ #

    async def _fetch_focus(self) -> Dict:
        focus = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for tentativa_filtro in (True, False):
                f = "Indicador eq 'IPCA'" + (" and Suavizado eq 'S'" if tentativa_filtro else "")
                focus["ipca"] = await self._odata(client, "ExpectativasMercadoAnuais",
                    filtro=f, campos="Indicador,Data,Media,Mediana,DataReferencia", top=8)
                if focus["ipca"]:
                    break

            for tentativa_filtro in (True, False):
                f = "Indicador eq 'IGP-M'" + (" and Suavizado eq 'S'" if tentativa_filtro else "")
                focus["igpm"] = await self._odata(client, "ExpectativasMercadoAnuais",
                    filtro=f, campos="Indicador,Data,Media,Mediana,DataReferencia", top=4)
                if focus["igpm"]:
                    break

            focus["selic"] = await self._odata(client, "ExpectativasMercadoReuniaoCopom",
                filtro=None, campos="Data,Reuniao,Media,Mediana", top=6)

        logger.info(
            f"[BCB] Focus: IPCA={len(focus.get('ipca',[]))} obs, "
            f"SELIC={len(focus.get('selic',[]))} obs"
        )
        return focus

    async def _odata(
        self, client: httpx.AsyncClient,
        endpoint: str, filtro: Optional[str],
        campos: str, top: int = 5,
    ) -> list:
        params = {
            "$top":     str(top),
            "$orderby": "Data desc",
            "$format":  "json",
            "$select":  campos,
        }
        if filtro:
            params["$filter"] = filtro

        try:
            resp = await client.get(f"{FOCUS_BASE}/{endpoint}", params=params)
            if resp.status_code == 200:
                return resp.json().get("value", [])
            logger.debug(f"[BCB Focus] {endpoint}: HTTP {resp.status_code}")
        except Exception as e:
            logger.debug(f"[BCB Focus] {endpoint}: {e}")
        return []

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _ultimo(self, series: Dict, nome: str) -> float:
        try:
            return round(float(series[nome].iloc[-1]), 4)
        except Exception:
            return 0.0

    def _acum12m(self, series: Dict, nome: str) -> float:
        try:
            s = series[nome].iloc[-12:]
            return round(float(((1 + s / 100).prod() - 1) * 100), 4)
        except Exception:
            return 0.0

    def _selic_proxima(self, focus: Dict) -> float:
        try:
            r = focus.get("selic", [])
            return round(float(r[0].get("Mediana") or 0), 2) if r else 0.0
        except Exception:
            return 0.0

    def _ipca_focus(self, focus: Dict) -> float:
        try:
            for r in focus.get("ipca", []):
                v = r.get("Media")
                if v:
                    return round(float(v), 2)
        except Exception:
            pass
        return 0.0

    def _curva_di(self, selic: float, focus: Dict) -> Dict[int, float]:
        if selic <= 0:
            return {}
        target = self._selic_proxima(focus) or selic * 0.95
        return {
            p: round(selic + (target - selic) * f, 4)
            for p, f in [(1,0),(3,0),(6,.1),(12,.3),(24,.6),(36,1),(60,1),(120,1)]
        }

    def _regime(self, series: Dict) -> str:
        try:
            s = series.get("selic_meta")
            if s is not None and len(s) >= 3:
                v = float(s.iloc[-1]) - float(s.iloc[-3])
                if v > 0.25:  return "abertura_spreads"
                if v < -0.25: return "fechamento_spreads"
        except Exception:
            pass
        return "neutro"
