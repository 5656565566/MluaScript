from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Callable

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from mluascript.frontends.tui.screens.web import WebScreen


class _ObservableWebService:
    def __init__(self) -> None:
        self.status = "stopped"
        self.url = "http://127.0.0.1:18080"
        self.last_error = ""
        self.listeners: set[Callable[[str], None]] = set()

    def configured_host_port(self) -> tuple[str, int]:
        return "127.0.0.1", 18080

    def subscribe(self, listener: Callable[[str], None]) -> Callable[[], None]:
        self.listeners.add(listener)
        listener(self.status)
        return lambda: self.listeners.discard(listener)

    def set_status(self, status: str) -> None:
        self.status = status
        for listener in tuple(self.listeners):
            listener(status)


class _WebScreenApp(App[None]):
    def __init__(self, web_service: _ObservableWebService) -> None:
        super().__init__()
        self.web_service = web_service

    def compose(self) -> ComposeResult:
        yield WebScreen()


def test_tui_can_close_web_without_revalidating_startup_inputs() -> None:
    operations: list[tuple[str, object]] = []
    controller = SimpleNamespace(status="running")
    screen = SimpleNamespace(
        app=SimpleNamespace(web_service=controller),
        _web_operation_active=False,
        _get_runtime_host_port=lambda: pytest.fail("关闭服务不应读取或校验启动地址"),
        _set_operation_active=lambda active: operations.append(("active", active)),
        _toggle_web_worker=lambda host, port, should_stop: operations.append(
            ("worker", (host, port, should_stop))
        ),
        notify=lambda *args, **kwargs: None,
    )

    WebScreen.action_toggle_web(screen)

    assert operations == [
        ("active", True),
        ("worker", (None, None, True)),
    ]


def test_web_screen_tracks_controller_status_after_mount() -> None:
    async def scenario() -> None:
        web_service = _ObservableWebService()
        app = _WebScreenApp(web_service)
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            assert str(app.query_one("#btn-toggle-web", Button).label) == "启动 Web"

            web_service.set_status("running")
            await pilot.pause()

            assert str(app.query_one("#btn-toggle-web", Button).label) == "关闭 Web"
            assert "Web 运行中" in str(app.query_one("#web-status", Static).render())

        assert not web_service.listeners

    asyncio.run(scenario())
