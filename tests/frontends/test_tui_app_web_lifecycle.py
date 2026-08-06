from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import mluascript.frontends.tui as tui_module
from mluascript.frontends.tui import TuiApp
from mluascript.control.state.models import TaskCapabilities, TaskListItemView
from mluascript.frontends.tui.components.pagination import paginate_items
from mluascript.frontends.tui.screens.run import RunScreen, _paginate_tasks
from mluascript.frontends.tui.screens.template_run import TemplateRunScreen
from mluascript.frontends.tui.screens.web import WebScreen
from mluascript.shared.config.models import WebServerConfig


class _FakeWebService:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def stop(self, **_kwargs) -> bool:
        self.events.append("web-stopped")
        return True


def _task_view(index: int) -> TaskListItemView:
    return TaskListItemView(
        task_id=f"task-{index}",
        kind="script",
        status="success",
        target="LOCAL",
        title=f"Task {index}",
        name=f"Task {index}",
        capabilities=TaskCapabilities(),
    )


def test_tui_task_list_paginates_newest_first() -> None:
    tasks = [_task_view(index) for index in range(45)]

    first, first_index, total_pages = _paginate_tasks(tasks, 0)
    last, last_index, _ = _paginate_tasks(tasks, 99)

    assert [task.task_id for task in first] == [f"task-{index}" for index in range(44, 34, -1)]
    assert first_index == 0
    assert total_pages == 5
    assert [task.task_id for task in last] == [f"task-{index}" for index in range(4, -1, -1)]
    assert last_index == 4


def test_tui_available_scripts_paginate_ten_per_page() -> None:
    scripts = [f"script-{index}.lua" for index in range(24)]

    first, first_index, total_pages = paginate_items(scripts, 0, 10)
    last, last_index, _ = paginate_items(scripts, 99, 10)

    assert first == scripts[:10]
    assert first_index == 0
    assert total_pages == 3
    assert last == scripts[20:]
    assert last_index == 2


def test_normal_quit_stops_web_before_textual_exit() -> None:
    events: list[str] = []
    app = SimpleNamespace(
        web_service=_FakeWebService(events),
        _has_running_tasks=lambda: False,
        notify=lambda *args, **kwargs: None,
        exit=lambda: events.append("app-exited"),
    )

    asyncio.run(TuiApp.action_quit(app))

    assert events == ["web-stopped", "app-exited"]


def test_force_quit_stops_tasks_and_web_before_textual_exit() -> None:
    events: list[str] = []
    app = SimpleNamespace(
        web_service=_FakeWebService(events),
        _stop_background_tasks=lambda: events.append("tasks-stopped") or 1,
        notify=lambda *args, **kwargs: None,
        exit=lambda: events.append("app-exited"),
    )

    asyncio.run(TuiApp._force_quit(app))

    assert events == ["tasks-stopped", "web-stopped", "app-exited"]


def test_tui_app_mounts_web_screen_with_owned_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tui_module.config_registry,
        "get",
        lambda config_type: WebServerConfig(enabled=False) if config_type is WebServerConfig else config_type(),
    )

    async def scenario() -> None:
        app = TuiApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query_one(WebScreen).app.web_service is app.web_service
            assert app.web_service.status == "stopped"
            assert app.web_service.worker is None

    asyncio.run(scenario())


def test_hidden_tui_pages_pause_periodic_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tui_module.config_registry,
        "get",
        lambda config_type: WebServerConfig(enabled=False) if config_type is WebServerConfig else config_type(),
    )

    async def scenario() -> None:
        app = TuiApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            run_screen = app.query_one(RunScreen)
            template_screen = app.query_one(TemplateRunScreen)
            assert run_screen._refresh_timer is not None
            assert template_screen._refresh_timer is not None
            assert run_screen._refresh_timer._active.is_set() is False
            assert template_screen._refresh_timer._active.is_set() is False

            app.action_switch_tab("run")
            await pilot.pause()
            assert run_screen._refresh_timer._active.is_set() is True
            assert template_screen._refresh_timer._active.is_set() is False

            app.action_switch_tab("home")
            await pilot.pause()
            assert run_screen._refresh_timer._active.is_set() is False

    asyncio.run(scenario())


def test_tui_artifact_readme_is_primary_action() -> None:
    source = Path(inspect.getsourcefile(RunScreen) or "").read_text(encoding="utf-8")

    assert 'f"查看说明 {label}"' in source
    assert 'run_button.label = "运行"' in source
    assert "Horizontal(readme_button, run_button" in source
