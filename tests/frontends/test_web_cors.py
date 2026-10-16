from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app
from mluascript.shared.config.models import WebServerConfig


def _client(monkeypatch, tmp_path: Path, origins: list[str] | None = None) -> TestClient:
    settings = WebServerConfig(
        password="secret-pass",
        session_secret="0123456789abcdef",
        project_roots=[str(tmp_path / "projects")],
        **({"cors_origins": origins} if origins is not None else {}),
    )
    monkeypatch.setattr(web_app, "_get_web_config", lambda: settings)
    return TestClient(web_app.create_web_app(tmp_path / "dist", runtime_dir=tmp_path, script_roots=[]))


def test_cors_is_disabled_by_default_without_breaking_same_origin_login(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    headers = {"Origin": "https://other.example"}
    response = client.get("/api/auth/status", headers=headers)
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers

    preflight = client.options(
        "/api/auth/login",
        headers={**headers, "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 405
    assert "access-control-allow-origin" not in preflight.headers

    assert client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"}).status_code == 200
    assert client.get("/api/auth/status").json()["data"]["authenticated"] is True


@pytest.mark.parametrize("origins", [["https://allowed.example"], ["*"]])
def test_cors_allows_configured_origins_with_credentials(monkeypatch, tmp_path, origins):
    client = _client(monkeypatch, tmp_path, origins)
    origin = "https://allowed.example"
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"

    client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    response = client.get("/api/auth/status", headers={"Origin": origin})
    assert response.json()["data"]["authenticated"] is True
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_origins_outside_the_allowlist(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, ["https://allowed.example"])
    headers = {"Origin": "https://other.example"}
    response = client.options(
        "/api/auth/login",
        headers={**headers, "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-origin" not in client.get("/api/auth/status", headers=headers).headers
