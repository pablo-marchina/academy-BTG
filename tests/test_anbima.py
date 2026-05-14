"""Testes para o coletor ANBIMA."""
import pytest
from unittest.mock import patch, AsyncMock


class TestANBIMA:
    def test_indexador_map(self):
        from src.collectors.anbima import INDEXADOR_MAP
        assert INDEXADOR_MAP["CDI"] == "cdi+"
        assert INDEXADOR_MAP["IPCA+"] == "ipca+"
        assert INDEXADOR_MAP["PRÉ"] == "pre"

    def test_norm_idx(self):
        from src.collectors.anbima import ANBIMACollector
        c = ANBIMACollector()
        assert c._norm_idx("CDI") == "cdi+"
        assert c._norm_idx("IPCA + 5%") == "ipca+"
        assert c._norm_idx("PREFIXADO") == "pre"
        assert c._norm_idx("") == ""

    @pytest.mark.asyncio
    async def test_collect_sem_credenciais(self):
        from src.collectors.anbima import ANBIMACollector
        c = ANBIMACollector()
        c._ativa = False
        ofertas, docs = await c.collect()
        assert ofertas == []
        assert docs == []

    def test_parse_curva(self):
        from src.collectors.anbima import ANBIMACollector
        c = ANBIMACollector()
        dados = {"Curva": [{"Vertice": 12, "Taxa": 14.5}, {"Vertice": 24, "Taxa": 13.8}]}
        curva = c._parse_curva(dados)
        assert curva[12] == 14.5
        assert curva[24] == 13.8

    def test_parse_curva_vazia(self):
        from src.collectors.anbima import ANBIMACollector
        c = ANBIMACollector()
        assert c._parse_curva({}) == {}
