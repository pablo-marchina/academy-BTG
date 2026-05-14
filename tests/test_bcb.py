"""Testes para o coletor BCB."""
import pytest
from unittest.mock import patch, AsyncMock


class TestBCB:
    def test_helpers_ultimo(self):
        from src.collectors.bcb_collector import BCBCollector
        import pandas as pd
        c = BCBCollector()
        series = {"selic_meta": pd.Series([14.25, 14.50])}
        assert c._ultimo(series, "selic_meta") == 14.50

    def test_helpers_ultimo_vazio(self):
        from src.collectors.bcb_collector import BCBCollector
        c = BCBCollector()
        assert c._ultimo({}, "nada") == 0.0

    def test_acum12m(self):
        from src.collectors.bcb_collector import BCBCollector
        import pandas as pd
        c = BCBCollector()
        series = {"ipca_mensal": pd.Series([0.5] * 12)}
        result = c._acum12m(series, "ipca_mensal")
        assert result > 6.0

    def test_regime(self):
        from src.collectors.bcb_collector import BCBCollector
        import pandas as pd
        c = BCBCollector()

        series_subindo = {"selic_meta": pd.Series([14.50, 14.50, 14.50])}
        assert c._regime(series_subindo) == "neutro"

        series_estavel = {"selic_meta": pd.Series([14.5, 14.5, 14.5])}
        assert c._regime(series_estavel) == "neutro"

    def test_curva_di(self):
        from src.collectors.bcb_collector import BCBCollector
        c = BCBCollector()
        curva = c._curva_di(14.5, {})
        assert 1 in curva
        assert curva[1] == 14.5
        assert 120 in curva

    @pytest.mark.asyncio
    async def test_collect_macro(self):
        from src.collectors.bcb_collector import BCBCollector
        import pandas as pd
        import numpy as np
        c = BCBCollector()

        with patch("src.collectors.bcb_collector.sgs.get") as mock_sgs:
            idx = pd.date_range("2025-01-01", periods=12, freq="ME")
            mock_sgs.return_value = pd.DataFrame({
                "selic_meta": [14.50] * 12,
                "ipca_mensal": [0.3] * 12,
                "igpm_mensal": [0.1] * 12,
                "ptax_dolar": [5.0] * 12,
            }, index=idx)

            with patch.object(c, "_fetch_focus", return_value={}):
                resultado = await c.collect_macro()
                assert resultado["selic_atual"] == 14.50

    @pytest.mark.asyncio
    async def test_fetch_focus_fallback(self):
        from src.collectors.bcb_collector import BCBCollector
        c = BCBCollector()

        with patch("httpx.AsyncClient.get") as mock_get:
            resp = AsyncMock()
            resp.status_code = 400
            mock_get.return_value = resp
            focus = await c._fetch_focus()
            assert focus.get("ipca") == []
