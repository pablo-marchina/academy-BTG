"""Testes do matching perfil x oferta."""
import pytest
from src.analytics.matching import (
    PerfilInvestidor,
    calcular_match,
    rankear_para_perfil,
)


class TestPerfilInvestidor:
    def test_conservador(self):
        p = PerfilInvestidor.conservador()
        assert p.nome == "Conservador"
        assert p.tolerancia_risco == "baixo"
        assert p.rating_minimo == "AA"

    def test_moderado(self):
        p = PerfilInvestidor.moderado()
        assert p.nome == "Moderado"
        assert p.indexador_preferido == "ipca+"

    def test_arrojado(self):
        p = PerfilInvestidor.arrojado()
        assert p.nome == "Arrojado"
        assert p.produto_preferido == "debenture"


class TestCalcularMatch:
    def test_match_excelente(self):
        oferta = {
            "produto": "debenture",
            "indexador": "IPCA+",
            "taxa_raw": "6.0",
            "rating": "AAA",
            "vencimento": "2030-01-01",
        }
        perfil = PerfilInvestidor.arrojado()
        r = calcular_match(oferta, perfil)
        assert r["match_score"] >= 60
        assert "excelente" in r["match_label"] or "boa" in r["match_label"]

    def test_rejeicao_ir(self):
        oferta = {
            "produto": "cdb",
            "indexador": "CDI",
            "taxa_raw": "1.0",
            "rating": "AAA",
        }
        perfil = PerfilInvestidor(nome="Teste", apenas_isento_ir=True)
        r = calcular_match(oferta, perfil)
        assert len(r["rejeicoes"]) > 0

    def test_rating_abaixo_rejeita(self):
        oferta = {
            "produto": "debenture",
            "rating": "B",
            "indexador": "CDI",
            "taxa_raw": "5.0",
        }
        perfil = PerfilInvestidor(nome="Teste", rating_minimo="AA")
        r = calcular_match(oferta, perfil)
        assert len(r["rejeicoes"]) > 0


class TestRankear:
    def test_rankear_para_perfil(self):
        ofertas = [
            {"produto": "cdb", "rating": "AAA", "taxa_raw": "1.0", "vencimento": "2027-01-01"},
            {"produto": "debenture", "rating": "BBB", "taxa_raw": "2.0", "vencimento": "2028-01-01"},
        ]
        perfil = PerfilInvestidor.conservador()
        ranking = rankear_para_perfil(ofertas, perfil, limite=5)
        assert len(ranking) <= 5
        assert ranking[0]["match"]["match_score"] >= ranking[-1]["match"]["match_score"]
