"""Testes para o gestor (StateGraph)."""
import pytest
from unittest.mock import patch


class TestBuildGestor:
    def test_gestor_compila(self):
        from src.agents.gestor import build_gestor
        g = build_gestor()
        nodes = list(g.get_graph().nodes)
        assert "__start__" in nodes
        assert "__end__" in nodes
        assert "coletar" in nodes
        assert "analisar" in nodes
        assert "sintetizar" in nodes

    def test_gestor_tem_11_nos(self):
        from src.agents.gestor import build_gestor
        g = build_gestor()
        assert len(list(g.get_graph().nodes)) == 11

    def test_gestor_edges(self):
        from src.agents.gestor import build_gestor
        g = build_gestor()
        edges = list(g.get_graph().edges)
        edge_pairs = [(str(e[0]), str(e[1])) for e in edges]
        assert ("coletar", "extrair") in edge_pairs
        assert ("analisar", "persistir_scores") in edge_pairs
        assert ("sintetizar", "__end__") in edge_pairs


@pytest.mark.slow
class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_run_pipeline_retorna_dict(self):
        from src.agents.gestor import run_pipeline
        from datetime import date
        with patch("src.collectors.pipeline.CollectionPipeline.run") as mock_run:
            mock_run.return_value = ([], [], {})
            with patch("src.collectors.pipeline.CollectionPipeline.fetch_curvas") as mock_c:
                mock_c.return_value = {}
                result = await run_pipeline(
                    data_inicio=date(2025, 1, 1),
                    data_fim=date(2025, 1, 31),
                    baixar_pdfs=False,
                )
                assert isinstance(result, dict)
                assert "analise" in result
                assert "ofertas" in result

    @pytest.mark.asyncio
    async def test_run_pipeline_com_erro(self):
        from src.agents.gestor import run_pipeline
        from datetime import date
        with patch("src.collectors.pipeline.CollectionPipeline.run", side_effect=Exception("Falha")) as mock_run:
            with patch("src.collectors.pipeline.CollectionPipeline.fetch_curvas") as mock_c:
                mock_c.return_value = {}
                result = await run_pipeline(
                    data_inicio=date(2025, 1, 1),
                    data_fim=date(2025, 1, 31),
                    baixar_pdfs=False,
                )
                assert "erros" in result
                assert len(result["erros"]) > 0
