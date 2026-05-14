"""Testes de integracao — validam que o pipeline completo carrega e executa."""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import date

pytestmark = pytest.mark.slow


class TestPipelineIntegration:
    def test_state_graph_compila(self):
        from src.agents.gestor import build_gestor
        g = build_gestor()
        nodes = list(g.get_graph().nodes)
        assert "__start__" in nodes
        assert "coletar" in nodes
        assert "analisar" in nodes
        assert "sintetizar" in nodes
        assert "__end__" in nodes

    @pytest.mark.asyncio
    async def test_run_pipeline_com_state(self):
        from src.agents.gestor import run_pipeline
        from src.agents.state import PipelineState

        with patch("src.collectors.pipeline.CollectionPipeline.run") as mock_run:
            mock_run.return_value = ([], [], {})
            with patch("src.collectors.pipeline.CollectionPipeline.fetch_curvas") as mock_curvas:
                mock_curvas.return_value = {}
                result = await run_pipeline(data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 31))
                assert isinstance(result, dict)
                assert "analise" in result

    def test_todos_coletores_importam(self):
        from src.collectors import (
            ANBIMACollector, BCBCollector, CVMCollector,
            PlatformCollector, CollectionPipeline,
            SecuritizadoraCollector, RICollector,
        )
        assert ANBIMACollector.name == "anbima"
        assert BCBCollector.name == "bcb"
        assert CVMCollector.name == "cvm"

    def test_fastapi_app_cria(self):
        from src.api.app import app
        routes = [r.path for r in app.routes]
        assert "/health" in routes
        assert "/metrics" in routes
        assert "/ofertas" in routes
        assert "/match" in routes
        assert "/stats" in routes
        assert "/ml/treinar" in routes
        assert "/ml/anomalias" in routes

    def test_ml_modelos_carregam(self):
        from src.analytics.score_xgb import prever_xgboost
        from src.analytics.score_ml import prever_score
        from src.analytics.anomalies import detectar_anomalia
        # Tests that modules compile - predictions require trained model
        assert callable(prever_xgboost)
        assert callable(prever_score)
        assert callable(detectar_anomalia)

    def test_notifiers_carregam(self):
        from src.notifiers.telegram import formatar_alerta_oferta, enviar_mensagem
        from src.notifiers.slack import enviar_slack
        from src.notifiers.multi_channel import alertar_todos_canais
        from src.notifiers.webhook import enviar_webhook
        assert callable(formatar_alerta_oferta)
        assert callable(enviar_mensagem)

    def test_exporters_carregam(self):
        from src.analytics.export_excel import exportar_ofertas_excel, exportar_analise_excel
        from src.analytics.relatorio import gerar_relatorio_research, gerar_relatorio_carteira
        assert callable(exportar_ofertas_excel)
        assert callable(gerar_relatorio_research)

    def test_cache_carregam(self):
        from src.db.cache import cache_get, cache_set, cache_delete
        assert callable(cache_get)
        assert callable(cache_set)

    def test_retention_carregam(self):
        from src.db.retention import limpar_dados_antigos
        assert callable(limpar_dados_antigos)

    def test_sentimento(self):
        from src.analytics.sentiment import analisar_sentimento, coletar_noticias
        r = analisar_sentimento("lucro recorde crescimento bom")
        assert r["sentimento"] == "positivo"
        assert r["score"] >= 0.6

    def test_anomalia_sem_dados(self):
        from src.analytics.anomalies import detectar_anomalia
        with patch("src.analytics.anomalies._carregar_features") as mock_features:
            import numpy as np
            mock_features.return_value = np.array([])
            r = detectar_anomalia({"spread_bps": 50, "score_total": 70, "volume_mm": 100})
            assert "erro" in r
