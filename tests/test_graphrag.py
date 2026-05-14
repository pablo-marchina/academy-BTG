"""Testes do GraphRAG."""
from src.vectorstore.graphrag import GraphRAG


class TestGraphRAG:
    def test_instancia(self):
        g = GraphRAG()
        r = g.resumo_mercado()
        assert isinstance(r, dict)
        assert "total_emissores" in r
        assert "total_coordenadores" in r
        assert "total_ofertas" in r

    def test_sem_dados_retorna_vazio(self):
        g = GraphRAG()
        ofertas = g.ofertas_por_emissor("EMPRESA_INEXISTENTE_XYZ")
        assert ofertas == []

        coordenadores = g.coordenadores_do_emissor("EMPRESA_INEXISTENTE_XYZ")
        assert coordenadores == []
