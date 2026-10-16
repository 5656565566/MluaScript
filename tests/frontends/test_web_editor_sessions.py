from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app


_SECRET = "editor-session-test-secret"


@pytest.fixture
def editor_app(monkeypatch, tmp_path):
    clock = SimpleNamespace(now=2_000_000_000)
    cfg = SimpleNamespace(
        username="admin", password="test-password", session_secret=_SECRET,
        session_max_age_seconds=60, project_roots=[str(tmp_path / "projects")],
    )
    monkeypatch.setattr(web_app, "time", SimpleNamespace(time=lambda: clock.now))
    monkeypatch.setattr(web_app, "_get_web_config", lambda: cfg)
    monkeypatch.setattr(web_app, "_EDITOR_SESSIONS", {})
    return web_app.create_web_app(tmp_path, runtime_dir=tmp_path, script_roots=[]), clock


def _token(clock, age=0):
    return web_app._encode_session_token("admin", clock.now - age, _SECRET)


def test_startup_cleanup_preserves_valid_draft_and_saved_files(editor_app, tmp_path):
    app, clock = editor_app
    valid = _token(clock)
    draft = web_app._create_empty_editor_session()
    draft["luaDocument"].update(content="print('unsaved')", dirty=True)
    draft["blocklyDocument"].update(xml="<xml>unsaved</xml>", dirty=True)
    invalid = [
        _token(clock, age=61),
        web_app._encode_session_token("other-user", clock.now, _SECRET),
        web_app._encode_session_token("admin", clock.now, "previous-secret"),
        "broken-token", "anonymous:127.0.0.1",
    ]
    web_app._EDITOR_SESSIONS.update({key: web_app._create_empty_editor_session() for key in invalid})
    web_app._EDITOR_SESSIONS[valid] = draft
    saved = tmp_path / "saved.lua"
    saved.write_text("print('saved')", encoding="utf-8")

    with TestClient(app) as client:
        assert list(web_app._EDITOR_SESSIONS) == [valid]
        client.cookies.set(web_app._AUTH_COOKIE_NAME, valid)
        response = client.get("/api/editor/session")
        assert response.status_code == 200
        assert response.json()["data"] == draft
        assert draft["luaDocument"]["dirty"] is True
        assert draft["blocklyDocument"]["dirty"] is True

    assert saved.read_text(encoding="utf-8") == "print('saved')"


@pytest.mark.parametrize("age, retained", [(59, True), (60, True), (61, False)])
def test_cleanup_uses_existing_login_expiration_boundary(editor_app, age, retained):
    app, clock = editor_app
    token = _token(clock, age=age)
    web_app._EDITOR_SESSIONS[token] = web_app._create_empty_editor_session()

    with TestClient(app) as client:
        assert (token in web_app._EDITOR_SESSIONS) is retained
        client.cookies.set(web_app._AUTH_COOKIE_NAME, token)
        response = client.get("/api/editor/session")
        assert response.status_code == (200 if retained else 401)


def test_periodic_cleanup_reclaims_expired_session_without_requests(editor_app, monkeypatch):
    app, clock = editor_app
    token = _token(clock)
    web_app._EDITOR_SESSIONS[token] = web_app._create_empty_editor_session()
    cleaned = Event()
    original_cleanup = web_app._cleanup_expired_editor_sessions

    def record_cleanup():
        original_cleanup()
        if token not in web_app._EDITOR_SESSIONS:
            cleaned.set()

    monkeypatch.setattr(web_app, "_cleanup_expired_editor_sessions", record_cleanup)
    monkeypatch.setattr(web_app, "_EDITOR_SESSION_CLEANUP_INTERVAL_SECONDS", 0.01)
    with TestClient(app):
        assert token in web_app._EDITOR_SESSIONS
        clock.now += 61
        assert cleaned.wait(timeout=2), "Expired session was not reclaimed while idle"


def test_logout_immediately_discards_only_current_session(editor_app):
    app, clock = editor_app
    current, other = _token(clock), _token(clock)
    web_app._EDITOR_SESSIONS.update({key: web_app._create_empty_editor_session() for key in (current, other)})

    with TestClient(app) as client:
        client.cookies.set(web_app._AUTH_COOKIE_NAME, current)
        assert client.post("/api/auth/logout").status_code == 200
        assert current not in web_app._EDITOR_SESSIONS
        assert other in web_app._EDITOR_SESSIONS


def test_cleanup_and_concurrent_sync_preserve_valid_clients(editor_app):
    _, clock = editor_app
    tokens = [_token(clock) for _ in range(8)]
    expired = _token(clock, age=61)
    web_app._EDITOR_SESSIONS[expired] = web_app._create_empty_editor_session()
    start = Barrier(len(tokens) + 1)

    def sync_session(index):
        request = SimpleNamespace(cookies={web_app._AUTH_COOKIE_NAME: tokens[index]})
        start.wait(timeout=3)
        for _ in range(100):
            payload = web_app.EditorSessionPayload(luaDocument={"content": f"draft-{index}", "dirty": True})
            response = web_app.put_editor_session(payload, request)
            assert response["data"]["luaDocument"]["content"] == f"draft-{index}"

    def cleanup():
        start.wait(timeout=3)
        for _ in range(100):
            web_app._cleanup_expired_editor_sessions()

    with ThreadPoolExecutor(max_workers=len(tokens) + 1) as pool:
        futures = [pool.submit(sync_session, index) for index in range(len(tokens))]
        futures.append(pool.submit(cleanup))
        for future in futures:
            future.result(timeout=5)

    assert set(web_app._EDITOR_SESSIONS) == set(tokens)
    for index, token in enumerate(tokens):
        assert web_app._EDITOR_SESSIONS[token]["luaDocument"]["content"] == f"draft-{index}"


def test_lifespan_cancels_and_awaits_cleanup_task(editor_app, monkeypatch):
    app, _ = editor_app
    started, finished = Event(), Event()
    tasks = []

    async def track_cleanup():
        tasks.append(asyncio.current_task())
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    monkeypatch.setattr(web_app, "_cleanup_editor_sessions_periodically", track_cleanup)
    with TestClient(app):
        assert started.wait(timeout=2)
        assert not finished.is_set()

    assert finished.is_set()
    assert tasks[0].cancelled()


def test_unauthenticated_requests_do_not_create_editor_sessions(editor_app):
    app, clock = editor_app
    with TestClient(app) as client:
        assert client.get("/api/editor/session").status_code == 401
        assert not web_app._EDITOR_SESSIONS
        client.cookies.set(web_app._AUTH_COOKIE_NAME, _token(clock, age=61))
        assert client.put("/api/editor/session", json={"luaDocument": {"content": "rejected"}}).status_code == 401
        assert not web_app._EDITOR_SESSIONS
