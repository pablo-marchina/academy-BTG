"""Testes para a API FastAPI."""
import pytest
from unittest.mock import patch

API_KEY_HEADER = {"Authorization": "Bearer test-key-123"}


@pytest.fixture(autouse=True)
def mock_api_keys():
    with patch("src.api.auth.API_KEYS", {"test-key-123"}):
        yield


class TestAPI:
    def test_app_cria(self):
        from src.api.app import app
        assert app.title == "BTG Intelligence API"
        routes = {r.path for r in app.routes}
        assert "/health" in routes
        assert "/metrics" in routes
        assert "/ofertas" in routes
        assert "/match" in routes
        assert "/stats" in routes

    def test_health_endpoint(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_stats_endpoint(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/stats", headers=API_KEY_HEADER)
        assert r.status_code == 200
        data = r.json()
        assert "total_ofertas" in data

    def test_match_endpoint_perfil_invalido(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.post("/match?perfil=invalido", headers=API_KEY_HEADER)
        assert r.status_code == 400

    def test_metrics_endpoint(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200
        assert b"btg_" in r.content

    def test_ofertas_endpoint(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/ofertas?limite=5", headers=API_KEY_HEADER)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sem_api_key_rejeitado(self):
        from src.api.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/stats")
        assert r.status_code == 401
