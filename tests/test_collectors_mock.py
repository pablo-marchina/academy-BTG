"""Testes de coletores com mock HTTP."""
import pytest
from unittest.mock import patch, AsyncMock


class TestANBIMAMock:
    @pytest.mark.asyncio
    async def test_anbima_sem_credenciais(self):
        from src.collectors.anbima import ANBIMACollector
        collector = ANBIMACollector()
        collector._ativa = False
        ofertas, docs = await collector.collect()
        assert ofertas == []
        assert docs == []


class TestBCBMock:
    @pytest.mark.asyncio
    async def test_bcb_series(self):
        from src.collectors.bcb_collector import BCBCollector
        import pandas as pd

        collector = BCBCollector()

        with patch("src.collectors.bcb_collector.sgs.get") as mock_sgs:
            mock_sgs.return_value = pd.DataFrame({
                "selic_meta": [14.25, 14.50],
                "ipca_mensal": [0.3, 0.4],
                "igpm_mensal": [0.1, 0.2],
                "ptax_dolar": [5.0, 5.1],
            })

            resultado = await collector.collect_macro()
            assert resultado["selic_atual"] == 14.50
            assert resultado["regime_mercado"] == "neutro"
            assert "curva_di" in resultado


class TestCVMMock:
    @pytest.mark.asyncio
    async def test_cvm_sem_arquivos(self):
        from src.collectors.cvm import CVMCollector
        from datetime import date

        collector = CVMCollector()
        async with collector:
            with patch.object(collector, "_listar_arquivos_ipe", return_value=[]):
                ofertas, docs = await collector.collect(data_inicio=date(2025, 1, 1))
                assert ofertas == []
                assert docs == []


class TestSecuritizadorasMock:
    @pytest.mark.asyncio
    async def test_securitizadoras_http_error(self):
        from src.collectors.securitizadoras import SecuritizadoraCollector
        collector = SecuritizadoraCollector()
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            resultados = await collector.collect()
            assert resultados == []


class TestBenchmark:
    def test_comparar_com_curva_di(self):
        from src.collectors.benchmark_anbima import comparar_com_benchmark
        curvas = {"di_pre": {12: 14.0, 24: 13.5}}
        oferta = {
            "produto": "debenture", "indexador": "CDI",
            "taxa_raw": "15.35", "vencimento": "2027-01-01",
        }
        r = comparar_com_benchmark(oferta, curvas)
        assert r["taxa_curva"] is not None
        assert r["premio_bps"] is not None
