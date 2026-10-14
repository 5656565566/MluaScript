from __future__ import annotations

import os
import socket
from pathlib import Path
from unittest.mock import call

import pytest
from playwright.sync_api import sync_playwright

from mluascript.maa.extensions.browser.controller import BrowserController


_EDGE = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"


def build_controller(mocker, *, connected: bool = True) -> BrowserController:
    controller = BrowserController.__new__(BrowserController)
    controller._handle = None
    controller._own = False
    controller._submit_browser = lambda operation: operation()
    controller._connected = connected
    controller.browser = None
    controller.page = mocker.MagicMock()
    controller.page.is_closed.return_value = False
    return controller


@pytest.mark.parametrize("contact, button", [(0, "left"), (1, "right"), (2, "middle")])
def test_browser_touch_callbacks_move_press_and_release_the_selected_button(mocker, contact, button) -> None:
    controller = build_controller(mocker)

    assert controller.touch_down(contact, 10, 20, 1) is True
    assert controller.touch_move(contact, 30, 40, 1) is True
    assert controller.touch_up(contact) is True
    assert controller.page.mouse.method_calls == [
        call.move(10, 20),
        call.down(button=button),
        call.move(30, 40),
        call.up(button=button),
    ]


@pytest.mark.parametrize("operation, args", [
    ("touch_down", (0, 10, 20, 1)),
    ("touch_move", (0, 10, 20, 1)),
    ("touch_up", (0,)),
])
def test_browser_touch_callbacks_do_not_operate_when_disconnected(mocker, operation, args) -> None:
    controller = build_controller(mocker, connected=False)

    assert getattr(controller, operation)(*args) is False
    assert controller.page.mouse.method_calls == []


@pytest.mark.parametrize("contact", [-1, 3, 100])
def test_browser_touch_callbacks_reject_unsupported_contacts_without_mouse_events(mocker, contact) -> None:
    controller = build_controller(mocker)
    warning = mocker.patch("mluascript.maa.extensions.browser.controller.logger.warning")

    assert controller.touch_down(contact, 10, 20, 1) is False
    assert controller.touch_move(contact, 10, 20, 1) is False
    assert controller.touch_up(contact) is False
    assert controller.page.mouse.method_calls == []
    assert warning.call_count == 3


@pytest.mark.parametrize("operation, args, failed_method", [
    ("touch_down", (0, 10, 20, 1), "move"),
    ("touch_down", (0, 10, 20, 1), "down"),
    ("touch_move", (0, 10, 20, 1), "move"),
    ("touch_up", (0,), "up"),
])
def test_browser_touch_callbacks_report_playwright_failures(mocker, operation, args, failed_method) -> None:
    controller = build_controller(mocker)
    getattr(controller.page.mouse, failed_method).side_effect = RuntimeError("Page closed")
    error = mocker.patch("mluascript.maa.extensions.browser.controller.logger.error")

    assert getattr(controller, operation)(*args) is False
    error.assert_called_once()
    if operation == "touch_down" and failed_method == "move":
        controller.page.mouse.down.assert_not_called()


@pytest.mark.parametrize("operation, args", [
    ("touch_down", (0, 10, 20, 1)),
    ("touch_move", (0, 10, 20, 1)),
    ("touch_up", (0,)),
])
def test_browser_touch_callbacks_use_the_existing_browser_worker(mocker, operation, args) -> None:
    controller = build_controller(mocker)
    submit = mocker.patch.object(controller, "_submit_browser")

    assert getattr(controller, operation)(*args) is True
    submit.assert_called_once()
    assert callable(submit.call_args.args[0])
    assert controller.page.mouse.method_calls == []
    submit.call_args.args[0]()
    assert controller.page.mouse.method_calls


@pytest.fixture
def native_browser_controller():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(_EDGE), headless=True, args=[f"--remote-debugging-port={port}"],
        )
        controller = BrowserController(f"http://127.0.0.1:{port}", browser_type="edge", name="touch-regression")
        try:
            assert controller.post_connection().wait().succeeded, controller.last_error

            def prepare_page() -> None:
                page = controller._current_page()
                page.goto("about:blank")
                page.set_viewport_size({"width": 1600, "height": 720})
                page.set_content('''
<style>body { margin: 0 } #target { position: absolute; left: 100px; top: 100px; width: 250px; height: 120px; }</style>
<button id="target">Click target</button>
<script>
window.mouseEvents = [];
window.clickCount = 0;
document.getElementById('target').addEventListener('click', () => window.clickCount++);
for (const type of ['mousedown', 'mousemove', 'mouseup']) {
    document.addEventListener(type, event => window.mouseEvents.push({
        type, button: event.button, buttons: event.buttons, x: event.clientX, y: event.clientY
    }));
}
document.addEventListener('contextmenu', event => event.preventDefault());
document.addEventListener('auxclick', event => event.preventDefault());
</script>''')

            controller._submit_browser(prepare_page)
            assert controller.post_screencap().wait().succeeded
            yield controller
        finally:
            worker = controller._browser_thread
            controller._close_transport()
            browser.close()
            assert worker is None or not worker.is_alive()


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt" or not _EDGE.is_file(), reason="Requires installed Windows Edge")
def test_native_maa_click_and_touch_drag_deliver_real_browser_mouse_events(native_browser_controller) -> None:
    controller = native_browser_controller

    def evaluate(expression: str):
        return controller._submit_browser(lambda: controller._current_page().evaluate(expression))

    assert controller.post_click(150, 140).wait().succeeded
    assert evaluate("window.clickCount") == 1
    events = evaluate("window.mouseEvents")
    assert [(event["type"], event["button"], event["x"], event["y"]) for event in events if event["type"] != "mousemove"] == [
        ("mousedown", 0, 150, 140), ("mouseup", 0, 150, 140),
    ]

    for contact, button, mask in [(0, 0, 1), (1, 2, 2), (2, 1, 4)]:
        evaluate("window.mouseEvents = []")
        assert controller.post_touch_down(450, 300, contact).wait().succeeded
        assert controller.post_touch_move(550, 350, contact).wait().succeeded
        assert controller.post_touch_up(contact).wait().succeeded
        events = evaluate("window.mouseEvents")
        down = next(event for event in events if event["type"] == "mousedown")
        up = next(event for event in events if event["type"] == "mouseup")
        assert (down["button"], down["buttons"], down["x"], down["y"]) == (button, mask, 450, 300)
        assert (up["button"], up["buttons"], up["x"], up["y"]) == (button, 0, 550, 350)
        assert any(event["type"] == "mousemove" and event["buttons"] == mask and event["x"] == 550 and event["y"] == 350 for event in events)

    evaluate("window.mouseEvents = []")
    assert controller.post_swipe(450, 300, 550, 350, 100).wait().succeeded
    events = evaluate("window.mouseEvents")
    assert any(event["type"] == "mousedown" and event["x"] == 450 and event["y"] == 300 for event in events)
    assert any(event["type"] == "mouseup" and event["x"] == 550 and event["y"] == 350 for event in events)

    evaluate("window.mouseEvents = []")
    assert not controller.post_touch_down(550, 350, 3).wait().succeeded
    assert not controller.post_touch_move(550, 350, 3).wait().succeeded
    assert not controller.post_touch_up(3).wait().succeeded
    assert evaluate("window.mouseEvents") == []


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt" or not _EDGE.is_file(), reason="Requires installed Windows Edge")
def test_native_browser_repeated_connect_and_cdp_reconnect_preserve_page(native_browser_controller) -> None:
    controller = native_browser_controller
    worker = controller._browser_thread
    owners = [(controller._browser_tasks, worker)]
    try:
        for _ in range(8):
            assert controller.post_connection().wait().succeeded, controller.last_error
            owners.append((controller._browser_tasks, controller._browser_thread))
            assert controller._browser_thread is worker
        controller._submit_browser(lambda: controller._current_page().evaluate("window.retainedValue = 42"))
        controller._submit_browser(lambda: controller.browser.close())
        assert controller.post_connection().wait().succeeded, controller.last_error
        owners.append((controller._browser_tasks, controller._browser_thread))
        assert not worker.is_alive()
        assert controller._submit_browser(lambda: controller._current_page().evaluate("window.retainedValue")) == 42
        assert controller.post_click(150, 140).wait().succeeded
        assert controller._submit_browser(lambda: controller._current_page().evaluate("window.clickCount")) == 1
    finally:
        for tasks, _ in owners:
            tasks.put(None)
        for _, owned_worker in owners:
            owned_worker.join(timeout=5)
            assert not owned_worker.is_alive()
