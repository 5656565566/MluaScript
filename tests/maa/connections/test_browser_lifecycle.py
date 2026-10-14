from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from mluascript.maa.extensions.browser.controller import BrowserController


@pytest.fixture
def browser(mocker, monkeypatch):
    controller = BrowserController.__new__(BrowserController)
    controller._handle = None
    controller._own = False
    controller.url = "http://127.0.0.1:9222"
    controller.executable_path = ""
    controller._connected = False
    controller.process = None
    controller.playwright = None
    controller.browser = None
    controller.page = None
    controller.last_error = ""
    controller._browser_tasks = None
    controller._browser_thread = None
    controller._connection_lock = threading.RLock()
    controller._browser_lock = threading.RLock()
    owners = []
    sessions = []
    entry = controller._browser_thread_main

    def tracked_entry(tasks, ready):
        owners.append((tasks, threading.current_thread()))
        entry(tasks, ready)

    controller._browser_thread_main = tracked_entry

    def start():
        owner = threading.get_ident()
        page = mocker.MagicMock()
        page.url = "https://test.invalid/"
        transport = mocker.MagicMock()
        transport.contexts = [mocker.MagicMock(pages=[page])]
        transport.is_connected.return_value = True
        playwright = mocker.MagicMock()
        playwright.chromium.connect_over_cdp.return_value = transport
        playwright.stop.side_effect = lambda: sessions.append((owner, threading.get_ident()))
        return playwright

    manager = mocker.MagicMock()
    manager.start.side_effect = start
    monkeypatch.setattr("mluascript.maa.extensions.browser.controller.sync_playwright", lambda: manager)
    yield controller, manager, sessions
    for tasks, _ in owners:
        tasks.put(None)
    for _, worker in owners:
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_repeated_connect_reuses_a_healthy_worker_and_page(browser) -> None:
    controller, manager, sessions = browser
    assert controller.connect() is True
    worker, page = controller._browser_thread, controller.page

    assert controller.connect() is True
    assert controller._browser_thread is worker
    assert controller.page is page
    assert manager.start.call_count == 1
    assert not sessions


def test_reconnect_stops_old_worker_on_its_owner_thread_before_replacement(browser) -> None:
    controller, manager, sessions = browser
    assert controller.connect() is True
    worker = controller._browser_thread
    controller.browser.is_connected.return_value = False

    assert controller.connect() is True
    assert not worker.is_alive()
    assert controller._browser_thread is not worker
    assert manager.start.call_count == 2
    assert sessions == [(worker.ident, worker.ident)]
    assert controller._submit_browser(lambda: "ready") == "ready"


def test_concurrent_connect_starts_only_one_worker(browser) -> None:
    controller, manager, _ = browser
    with ThreadPoolExecutor(max_workers=8) as callers:
        assert all(callers.map(lambda _: controller.connect(), range(8)))
    assert manager.start.call_count == 1
    assert controller._browser_thread.is_alive()


def test_browser_does_not_fall_back_to_callers_thread_without_worker(browser, mocker) -> None:
    controller, _, _ = browser
    operation = mocker.Mock()
    with pytest.raises(RuntimeError):
        controller._submit_browser(operation)
    operation.assert_not_called()


def test_reconnect_retains_a_worker_that_does_not_exit_and_refuses_replacement(browser, mocker) -> None:
    controller, _, _ = browser
    worker = mocker.Mock()
    worker.is_alive.return_value = True
    controller._browser_thread = worker
    controller._browser_tasks = tasks = queue.Queue()
    replacement = mocker.patch.object(controller, "_start_browser_thread")

    assert controller.connect() is False
    assert controller._browser_thread is worker
    assert controller._browser_tasks is tasks
    assert "worker" in controller.last_error.lower()
    replacement.assert_not_called()


def test_connection_failure_cleans_worker_and_next_connection_can_succeed(browser) -> None:
    controller, manager, _ = browser
    start = manager.start.side_effect
    manager.start.side_effect = RuntimeError("CDP unavailable")

    assert controller.connect() is False
    assert controller.last_error == "CDP unavailable"
    assert controller._browser_thread is None
    assert controller._browser_tasks is None
    manager.start.side_effect = start
    assert controller.connect() is True
    assert controller._submit_browser(lambda: "recovered") == "recovered"


def test_thread_start_failure_returns_false_without_joining_unstarted_thread(browser, mocker) -> None:
    controller, _, _ = browser
    mocker.patch("mluascript.maa.extensions.browser.controller.threading.Thread.start", side_effect=RuntimeError("Cannot start thread"))

    assert controller.connect() is False
    assert controller.last_error == "Cannot start thread"
    assert controller._browser_thread is None
    assert controller._browser_tasks is None


def test_reconnect_reuses_its_running_browser_process(browser, mocker) -> None:
    controller, _, _ = browser
    assert controller.connect() is True
    controller.browser.is_connected.return_value = False
    controller.executable_path = "browser.exe"
    process = mocker.Mock()
    process.poll.return_value = None
    controller.process = process
    launch = mocker.patch.object(controller, "_launch_browser_process")
    endpoint = mocker.patch.object(controller, "_wait_for_debug_endpoint")

    assert controller.connect() is True
    assert controller.process is process
    launch.assert_not_called()
    endpoint.assert_called_once()
    process.terminate.assert_not_called()


def test_close_fails_queued_operations_and_allows_current_operation_to_finish(browser, mocker) -> None:
    controller, _, sessions = browser
    assert controller.connect() is True
    entered, release = threading.Event(), threading.Event()
    queued = mocker.Mock()

    def running():
        entered.set()
        assert release.wait(timeout=5)
        return "finished"

    with ThreadPoolExecutor(max_workers=3) as callers:
        first = callers.submit(controller._submit_browser, running)
        try:
            assert entered.wait(timeout=3)
            second = callers.submit(controller._submit_browser, queued)
            deadline = time.monotonic() + 3
            while controller._browser_tasks.empty() and time.monotonic() < deadline:
                threading.Event().wait(0.005)
            assert not controller._browser_tasks.empty()
            closing = callers.submit(controller._close_transport)
            with pytest.raises(RuntimeError):
                second.result(timeout=1)
            queued.assert_not_called()
        finally:
            release.set()
        assert first.result(timeout=3) == "finished"
        closing.result(timeout=3)

    assert controller._browser_thread is None
    assert controller._browser_tasks is None
    assert controller.connected() is False
    assert all(started == stopped for started, stopped in sessions)
