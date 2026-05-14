"""Testes do DBSCAN clustering."""
import pytest
import numpy as np
from src.analytics.clustering import (
    clusterizar_ofertas,
    extrair_features,
    _numerar_rating,
    _numerar_produto,
)


class TestClustering:
    def test_cluster_duas_ofertas_iguais(self):
        ofertas = [
            {"produto": "debenture", "indexador": "CDI", "spread_bps": 100, "prazo_meses": 24, "volume_mm": 100, "rating": "AAA"},
            {"produto": "debenture", "indexador": "CDI", "spread_bps": 100, "prazo_meses": 24, "volume_mm": 100, "rating": "AAA"},
        ]
        resultado = clusterizar_ofertas(ofertas, eps=0.5, min_samples=1)
        assert len(resultado) == 2
        assert resultado[0]["cluster"] >= 0

    def test_cluster_oferta_unica(self):
        ofertas = [
            {"produto": "cdb", "indexador": "CDI", "spread_bps": 50, "prazo_meses": 6, "volume_mm": 10, "rating": "AA"},
        ]
        resultado = clusterizar_ofertas(ofertas, min_samples=2)
        assert resultado[0]["cluster"] == -1

    def test_vazio(self):
        resultado = clusterizar_ofertas([])
        assert resultado == []

    def test_features_shape(self):
        ofertas = [
            {"spread_bps": 100, "prazo_meses": 24, "volume_mm": 50, "rating": "AAA", "produto": "debenture", "indexador": "CDI+"},
        ]
        X = extrair_features(ofertas)
        assert X.shape == (1, 6)


class TestHelpers:
    def test_numerar_rating(self):
        assert _numerar_rating("AAA") == 1.0
        assert _numerar_rating("D") == 0.0
        assert _numerar_rating(None) == 0.5
        assert _numerar_rating("") == 0.5

    def test_numerar_produto(self):
        assert _numerar_produto("cdb") == 0
        assert _numerar_produto("debenture") == 3
        assert _numerar_produto("fii") == 4
        assert _numerar_produto("desconhecido") == 6
