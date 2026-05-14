"""Testes do score de atratividade."""
import pytest
from src.analytics.score import (
    calcular_score,
    calcular_rating_pontos,
    calcular_garantia_pontos,
    RATING_PONTOS,
    GARANTIA_PONTOS,
)


class TestCalcularRatingPontos:
    def test_aaa(self):
        assert calcular_rating_pontos("AAA") == RATING_PONTOS["AAA"]

    def test_aa_mais(self):
        assert calcular_rating_pontos("AA+") == RATING_PONTOS["AA+"]

    def test_none(self):
        assert calcular_rating_pontos(None) == 0

    def test_vazio(self):
        assert calcular_rating_pontos("") == 0


class TestCalcularGarantiaPontos:
    def test_real(self):
        assert calcular_garantia_pontos("real") == GARANTIA_PONTOS["real"]

    def test_fidejussoria(self):
        assert calcular_garantia_pontos("fidejussoria") == GARANTIA_PONTOS["fidejussoria"]

    def test_vazio(self):
        assert calcular_garantia_pontos("") == GARANTIA_PONTOS[""]


class TestCalcularScore:
    def test_score_basico(self):
        oferta = {
            "produto": "debenture",
            "indexador": "CDI",
            "taxa_raw": "1.35",
            "rating": "AA+",
            "coordenador": "BTG",
            "codigo": "ABC123",
            "vencimento": "2030-01-01",
        }
        normalizado = {"spread_bps": 80}
        r = calcular_score(oferta, normalizado)
        assert 0 <= r["score_total"] <= 100
        assert 0 <= r["score_confianca"] <= 1
        assert "decomposicao" in r
        assert "componentes" in r

    def test_sem_rating_diminui_score(self):
        oferta_com = {"rating": "AAA", "codigo": "X", "vencimento": "2030-01-01"}
        oferta_sem = {"rating": None, "codigo": "Y", "vencimento": "2030-01-01"}
        r_com = calcular_score(oferta_com, {})
        r_sem = calcular_score(oferta_sem, {})
        assert r_com["score_total"] > r_sem["score_total"]

    def test_confidence_cai_sem_codigo(self):
        oferta = {"codigo": "", "vencimento": "2030-01-01"}
        r = calcular_score(oferta, normalizado={"spread_bps": 50})
        assert r["score_confianca"] < 1.0
