from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app
from mluascript.frontends.web.preferences import WebPreferences, WebPreferenceService


def _web_config(project_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        username="admin",
        password="secret-pass",
        session_secret="0123456789abcdef",
        session_max_age_seconds=3600,
        project_roots=[str(project_root)],
    )


def _client(monkeypatch, tmp_path: Path, *, login: bool = True) -> tuple[TestClient, Path]:
    monkeypatch.setattr(web_app, "_get_web_config", lambda: _web_config(tmp_path / "projects"))
    preference_path = tmp_path / "settings" / "preferences.json"
    client = TestClient(web_app.create_web_app(tmp_path / "dist", preferences_path=preference_path))
    if login:
        response = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
        assert response.status_code == 200
    return client, preference_path


def test_web_preferences_require_authentication(monkeypatch, tmp_path: Path) -> None:
    client, _ = _client(monkeypatch, tmp_path, login=False)

    assert client.get("/api/system/preferences").status_code == 401
    assert client.put("/api/system/preferences", json={}).status_code == 401


def test_web_preferences_persist_and_reload_without_secrets(monkeypatch, tmp_path: Path) -> None:
    client, preference_path = _client(monkeypatch, tmp_path)
    defaults = client.get("/api/system/preferences")
    assert defaults.status_code == 200
    preferences = defaults.json()["data"]
    preferences["appearance"] = {
        "themeMode": "dark",
        "colorTheme": "custom",
        "customColor": "#2080f0",
        "paletteVersion": 1,
    }
    preferences["editor"]["autoSaveFiles"] = False

    saved = client.put("/api/system/preferences", json=preferences)

    assert saved.status_code == 200
    assert saved.json()["data"]["appearance"]["colorTheme"] == "custom"
    assert saved.json()["data"]["appearance"]["customColor"] == "#2080f0"
    assert not list(preference_path.parent.glob(f".{preference_path.name}.*.tmp"))
    stored_text = preference_path.read_text(encoding="utf-8")
    assert "secret-pass" not in stored_text
    assert "0123456789abcdef" not in stored_text

    reloaded, _ = _client(monkeypatch, tmp_path)
    restored = reloaded.get("/api/system/preferences")
    assert restored.status_code == 200
    assert restored.json()["data"]["editor"]["autoSaveFiles"] is False
    assert restored.json()["data"]["appearance"]["themeMode"] == "dark"


def test_web_preferences_reject_unknown_and_secret_fields(monkeypatch, tmp_path: Path) -> None:
    client, preference_path = _client(monkeypatch, tmp_path)
    payload = client.get("/api/system/preferences").json()["data"]
    payload["sessionSecret"] = "must-not-be-accepted"

    response = client.put("/api/system/preferences", json=payload)

    assert response.status_code == 422
    assert not preference_path.exists()


def test_preference_service_separates_users_and_recovers_from_invalid_document(tmp_path: Path) -> None:
    preference_path = tmp_path / "preferences.json"
    service = WebPreferenceService(preference_path)
    admin = WebPreferences.model_validate({"appearance": {"themeMode": "dark", "colorTheme": "violet"}})
    operator = WebPreferences.model_validate({"editor": {"autoSaveFiles": False}})

    service.put("admin", admin)
    service.put("operator", operator)

    assert service.get("admin").appearance.color_theme == "violet"
    assert service.get("admin").editor.auto_save_files is True
    assert service.get("operator").appearance.theme_mode == "system"
    assert service.get("operator").editor.auto_save_files is False
    assert set(json.loads(preference_path.read_text(encoding="utf-8"))["users"]) == {"admin", "operator"}

    preference_path.write_text('{"schemaVersion": 1, "users": {"admin": {"sessionSecret": "bad"}}}', encoding="utf-8")
    assert service.get("admin") == WebPreferences()


def test_legacy_accent_color_migrates_to_custom_palette() -> None:
    preferences = WebPreferences.model_validate(
        {"appearance": {"themeMode": "light", "accentColor": "#2080f0"}}
    )

    assert preferences.appearance.color_theme == "custom"
    assert preferences.appearance.custom_color == "#2080f0"
    dumped = preferences.model_dump(by_alias=True)
    assert "accentColor" not in dumped["appearance"]
