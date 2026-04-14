from fastapi.testclient import TestClient

from lethargy.api.app import create_app


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
