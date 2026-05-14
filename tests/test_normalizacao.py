"""Testes da normalização financeira."""
import pytest
from src.analytics.normalizacao import (
    normalizar_taxa,
    gross_up_ir,
    spread_vs_curva,
    normalizar_oferta,
    PRODUTOS_ISENTOS,
)


class TestNormalizarTaxa:
    def test_cdi_mais(self):
        r = normalizar_taxa("1.35", "CDI")
        assert r["taxa_cdi"] == 1.35
        assert r["taxa_ipca"] is None
        assert r["taxa_pre"] is None

    def test_ipca_mais(self):
        r = normalizar_taxa("5.5", "IPCA+")
        assert r["taxa_ipca"] == 5.5

    def test_pre(self):
        r = normalizar_taxa("13.75", "PRE")
        assert r["taxa_pre"] == 13.75

    def test_virgula_decimal(self):
        r = normalizar_taxa("1,35", "CDI")
        assert r["taxa_cdi"] == 1.35

    def test_vazio(self):
        r = normalizar_taxa("", "CDI")
        assert r["taxa_cdi"] is None
        assert r["taxa_ipca"] is None
        assert r["taxa_pre"] is None


class TestGrossUpIR:
    def test_produto_isento(self):
        for p in PRODUTOS_ISENTOS:
            r = gross_up_ir(1.5, p, 365)
            assert r["aliquota_ir"] == 0.0
            assert r["taxa_liquida"] == 1.5

    def test_debenture_ate_180d(self):
        r = gross_up_ir(1.5, "debenture", 90)
        assert r["aliquota_ir"] == 22.5
        assert round(r["taxa_liquida"], 4) == 1.1625

    def test_debenture_ate_360d(self):
        r = gross_up_ir(1.5, "debenture", 200)
        assert r["aliquota_ir"] == 20.0

    def test_debenture_acima_720d(self):
        r = gross_up_ir(1.5, "debenture", 800)
        assert r["aliquota_ir"] == 15.0


class TestSpreadVsCurva:
    def test_com_curva(self):
        curvas = {"di_pre": {12: 14.0}}
        r = spread_vs_curva(15.35, "CDI", 12, curvas)
        assert r["spread_bps"] == 135.0
        assert r["taxa_curva"] == 14.0

    def test_sem_curva(self):
        curvas = {}
        r = spread_vs_curva(15.0, "CDI", 12, curvas)
        assert r["spread_bps"] is None


class TestNormalizarOferta:
    def test_oferta_completa(self):
        oferta = {
            "produto": "debenture",
            "indexador": "CDI",
            "taxa_raw": "1.35",
            "vencimento": "2030-01-01",
        }
        r = normalizar_oferta(oferta)
        assert r["taxa_cdi"] == 1.35
        assert r["prazo_dias"] > 0
        assert r["aliquota_ir"] == 15.0
