"""Testes para o pipeline de coleta."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date
from typing import List


class TestDeduplicacao:
    def test_dedup_mantem_melhor_fonte(self):
        from src.collectors.pipeline import CollectionPipeline, PRIORIDADE_FONTE
        from src.models.raw import RawOffer
        p = CollectionPipeline()
        ofertas = [
            RawOffer(codigo="ABC123", fonte="btg_html", emissor="Empresa A", produto="debenture"),
            RawOffer(codigo="ABC123", fonte="anbima", emissor="Empresa A", produto="debenture"),
        ]
        resultado = p._deduplicar(ofertas)
        assert len(resultado) == 1
        assert resultado[0]["fonte"] == "anbima"

    def test_dedup_sem_codigo_mantem_todos(self):
        from src.collectors.pipeline import CollectionPipeline
        from src.models.raw import RawOffer
        p = CollectionPipeline()
        ofertas = [
            RawOffer(codigo="", fonte="btg_html", emissor="A"),
            RawOffer(codigo="", fonte="xp_html", emissor="B"),
        ]
        resultado = p._deduplicar(ofertas)
        assert len(resultado) == 2

    def test_dedup_oferta_unica(self):
        from src.collectors.pipeline import CollectionPipeline
        from src.models.raw import RawOffer
        p = CollectionPipeline()
        ofertas = [RawOffer(codigo="UNICO", fonte="anbima")]
        resultado = p._deduplicar(ofertas)
        assert len(resultado) == 1

    def test_dedup_vazio(self):
        from src.collectors.pipeline import CollectionPipeline
        p = CollectionPipeline()
        assert p._deduplicar([]) == []

    def test_prioridade_fonte_anbima_mais_confiavel(self):
        from src.collectors.pipeline import PRIORIDADE_FONTE
        assert PRIORIDADE_FONTE["anbima"] < PRIORIDADE_FONTE["cvm"]
        assert PRIORIDADE_FONTE["cvm"] < PRIORIDADE_FONTE["btg_api"]


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_run_consolida_resultados(self):
        from src.collectors.pipeline import CollectionPipeline
        from src.models.raw import RawOffer, RawDocument
        p = CollectionPipeline()

        with patch.object(p, "_run_anbima", return_value=([RawOffer(codigo="A1", fonte="anbima")], [])):
            with patch.object(p, "_run_cvm", return_value=([], [])):
                with patch.object(p, "_run_platforms", return_value=([RawOffer(codigo="B1", fonte="btg_api")], [])):
                    with patch.object(p, "_run_macro", return_value={"selic_atual": 14.5}):
                        ofertas, docs, macro = await p.run(
                            data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 31)
                        )
                        assert len(ofertas) == 2
                        assert macro["selic_atual"] == 14.5

    @pytest.mark.asyncio
    async def test_run_com_erro_parcial(self):
        from src.collectors.pipeline import CollectionPipeline
        from src.models.raw import RawOffer
        p = CollectionPipeline()

        with patch.object(p, "_run_anbima", side_effect=Exception("ANBIMA falhou")):
            with patch.object(p, "_run_cvm", return_value=([RawOffer(codigo="C1", fonte="cvm")], [])):
                with patch.object(p, "_run_platforms", return_value=([], [])):
                    with patch.object(p, "_run_macro", return_value={}):
                        ofertas, docs, macro = await p.run(
                            data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 31)
                        )
                        assert len(ofertas) == 1
                        assert ofertas[0]["fonte"] == "cvm"

    @pytest.mark.asyncio
    async def test_run_sem_pdfs(self):
        from src.collectors.pipeline import CollectionPipeline
        from src.models.raw import RawOffer, RawDocument
        p = CollectionPipeline()

        with patch.object(p, "_run_anbima", return_value=([], [RawDocument(url="http://pdf.com/doc.pdf")])):
            with patch.object(p, "_run_cvm", return_value=([], [])):
                with patch.object(p, "_run_platforms", return_value=([], [])):
                    with patch.object(p, "_run_macro", return_value={}):
                        with patch.object(p, "cvm") as mock_cvm:
                            mock_cvm.download_todos = AsyncMock(return_value=[])
                            ofertas, docs, macro = await p.run(
                                data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 31),
                                baixar_pdfs=False
                            )
                            assert len(docs) == 1
