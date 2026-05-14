"""Testes para analytics (ML, export, relatorio)."""
import pytest
from unittest.mock import patch


class TestScoreML:
    def test_prever_sem_modelo(self):
        from src.analytics.score_ml import prever_score
        with patch("src.analytics.score_ml._carregar_treino") as mock:
            import pandas as pd
            mock.return_value = pd.DataFrame()
            r = prever_score({"produto": "cdb", "spread_bps": 50})
            assert "erro" in r or "score_ml" in r

    def test_rating_num_interno(self):
        from src.analytics.score_ml import _rating_num
        assert _rating_num("AAA") == 10
        assert _rating_num("BBB+") == 3
        assert _rating_num(None) == 0


class TestScoreXGB:
    def test_prever_sem_modelo(self):
        from src.analytics.score_xgb import prever_xgboost
        r = prever_xgboost({"produto": "debenture", "spread_bps": 80, "rating": "AA", "volume_mm": 50})
        assert "score_xgb" in r or "erro" in r

    def test_rating_num(self):
        from src.analytics.score_xgb import _rating_num
        assert _rating_num("AAA") == 10
        assert _rating_num("") == 0


class TestAnomalies:
    def test_deteccao_sem_dados(self):
        from src.analytics.anomalies import detectar_anomalia
        with patch("src.analytics.anomalies._carregar_features") as mock:
            import numpy as np
            mock.return_value = np.array([])
            r = detectar_anomalia({"spread_bps": 50, "score_total": 70, "volume_mm": 100})
            assert "erro" in r


class TestExport:
    def test_exportar_ofertas_excel(self, tmp_path):
        from src.analytics.export_excel import exportar_ofertas_excel
        ofertas = [{"codigo": "ABC", "emissor": "Teste", "produto": "cdb"}]
        caminho = str(tmp_path / "test.xlsx")
        resultado = exportar_ofertas_excel(ofertas, caminho)
        assert resultado.endswith(".xlsx")
        import os
        assert os.path.exists(resultado)


class TestRelatorio:
    def test_relatorio_research(self, tmp_path):
        from src.analytics.relatorio import gerar_relatorio_research
        ofertas = [{"emissor": "Teste", "produto": "debenture", "score": 80}]
        caminho = str(tmp_path / "test.pdf")
        resultado = gerar_relatorio_research(ofertas, caminho)
        assert resultado.endswith(".pdf")
        import os
        assert os.path.exists(resultado)
