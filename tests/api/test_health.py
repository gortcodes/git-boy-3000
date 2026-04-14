from fastapi.testclient import TestClient

from lethargy.api.app import create_app
from lethargy.config import get_settings


def test_healthz_returns_ok():
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_metrics_endpoint_exposes_prometheus_text():
    with TestClient(create_app()) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert b"http_requests_total" in response.content


def test_privacy_endpoint_reports_contact(monkeypatch):
    monkeypatch.setenv("LETHARGY_PRIVACY_CONTACT", "privacy-test@example.com")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/privacy")
        assert response.status_code == 200
        body = response.json()
        assert body["contact"] == "privacy-test@example.com"
        assert "removal" in body["removal_requests"].lower()
        assert isinstance(body["data_retained"], list)
    finally:
        get_settings.cache_clear()
