"""Testes para os notifiers."""
import pytest
from unittest.mock import patch


class TestTelegram:
    def test_formatar_alerta(self):
        from src.notifiers.telegram import formatar_alerta_oferta
        oferta = {"produto": "debenture", "emissor": "Teste SA", "taxa_raw": "CDI+1.5%", "indexador": "CDI"}
        msg = formatar_alerta_oferta(oferta)
        assert "CDI" in msg
        assert "Teste" in msg

    def test_enviar_sem_token(self):
        from src.notifiers.telegram import enviar_mensagem
        with patch("src.config.settings.TELEGRAM_BOT_TOKEN", ""):
            assert enviar_mensagem("teste") is False

    def test_watchlist(self):
        from src.notifiers.telegram import adicionar_watchlist, remover_watchlist, EMISSORES_WATCHLIST
        adicionar_watchlist("Petrobras")
        assert "Petrobras" in EMISSORES_WATCHLIST
        remover_watchlist("Petrobras")
        assert "Petrobras" not in EMISSORES_WATCHLIST


class TestMultiChannel:
    def test_alertar_todos_canais_vazio(self):
        from src.notifiers.multi_channel import alertar_todos_canais
        r = alertar_todos_canais([], [], {}, canais=[])
        assert r == {}
