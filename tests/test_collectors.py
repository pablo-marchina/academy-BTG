"""Testes para coletores."""
import pytest
from unittest.mock import patch, AsyncMock


class TestBaseCollector:
    def test_rate_limiter(self):
        from src.collectors.base import RateLimiter
        rl = RateLimiter(max_requests=10, window_seconds=1.0)
        assert rl.max_requests == 10

    def test_get_http_client(self):
        from src.collectors.base import get_http_client
        client = get_http_client()
        assert client is not None


class TestSecuritizadoras:
    def test_detectar_produto(self):
        from src.collectors.securitizadoras import SecuritizadoraCollector
        c = SecuritizadoraCollector()
        assert c._detectar_produto("CRA emission") == "cra"
        assert c._detectar_produto("CRI test") == "cri"
        assert c._detectar_produto("FII fund") == "fii"
        assert c._detectar_produto("unknown") == "outro"

    def test_detectar_indexador(self):
        from src.collectors.securitizadoras import SecuritizadoraCollector
        c = SecuritizadoraCollector()
        assert c._detectar_indexador("CDI + 1.5%") == "cdi+"
        assert c._detectar_indexador("IPCA + 5%") == "ipca+"
        assert c._detectar_indexador("PRE 13%") == "pre"

    def test_extrair_taxa(self):
        from src.collectors.securitizadoras import SecuritizadoraCollector
        c = SecuritizadoraCollector()
        taxa1 = c._extrair_taxa("taxa de 1.35% a.a.")
        assert "1.35" in taxa1
        assert c._extrair_taxa("1,5x CDI") == "1,5x CDI"


class TestBenchmark:
    def test_comparar_sem_curvas(self):
        from src.collectors.benchmark_anbima import comparar_com_benchmark
        r = comparar_com_benchmark({})
        assert r["benchmark"] is None

    def test_comparar_com_curva(self):
        from src.collectors.benchmark_anbima import comparar_com_benchmark
        curvas = {"di_pre": {12: 14.0}}
        r = comparar_com_benchmark(
            {"produto": "debenture", "indexador": "CDI", "taxa_raw": "15.35", "vencimento": "2030-01-01"},
            curvas,
        )
        assert r["taxa_curva"] == 14.0
        assert r["premio_bps"] == 135.0
