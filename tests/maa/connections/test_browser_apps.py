import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Error, sync_playwright

from mluascript.maa.extensions.browser.controller import BrowserController


_EDGE = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "nt" or not _EDGE.is_file(), reason="Requires installed Windows Edge"),
]


@pytest.fixture
def native_browser():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(_EDGE), headless=True, args=[f"--remote-debugging-port={port}"],
        )
        controller = BrowserController(f"http://127.0.0.1:{port}", browser_type="edge", name="app-regression")
        try:
            assert controller.post_connection().wait().succeeded, controller.last_error
            controller._submit_browser(lambda: controller._current_page().set_viewport_size({"width": 1600, "height": 720}))
            assert controller.post_screencap().wait().succeeded
            yield controller, browser
        finally:
            controller._close_transport()
            browser.close()


@pytest.fixture
def website():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = b'''<!doctype html><title>Browser application test</title>
<style>body{margin:0}button{position:absolute;left:100px;top:100px;width:250px;height:120px}</style>
<button onclick="window.clicks++">Click</button><script>window.clicks=0</script>'''
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/page"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        assert not worker.is_alive()


def test_native_start_app_opens_a_web_page_and_keeps_mouse_operations_working(native_browser, website):
    controller, _ = native_browser
    assert controller.post_start_app(website).wait().succeeded, controller.last_error
    assert controller._submit_browser(lambda: controller._current_page().url) == website
    assert controller.post_click(150, 140).wait().succeeded
    assert controller._submit_browser(lambda: controller._current_page().evaluate("window.clicks")) == 1


@pytest.mark.parametrize("separate_context", [False, True])
def test_native_stop_app_preserves_other_pages_and_closes_browser_only_after_last_page(native_browser, separate_context):
    controller, browser = native_browser

    def add_page():
        context = controller.browser.new_context() if separate_context else controller.browser.contexts[0]
        original = controller._current_page()
        other = context.new_page()
        other.set_content("<title>Keep this page</title>")
        return original, other

    original, other = controller._submit_browser(add_page)
    worker = controller._browser_thread
    assert controller.post_stop_app("current-page").wait().succeeded, controller.last_error
    assert controller._submit_browser(lambda: original.is_closed())
    assert controller._submit_browser(lambda: not other.is_closed() and other.title() == "Keep this page")
    assert controller.connected()
    assert controller._browser_thread is worker
    assert controller.post_stop_app("current-page").wait().succeeded, controller.last_error
    assert not controller.connected()
    assert controller._browser_thread is None
    assert not worker.is_alive()
    # 使用另一条 Playwright 连接验证进程确实关闭，而非仅断开控制器的 CDP。
    with pytest.raises(Error, match="closed|Target"):
        browser.new_context()


def test_native_navigation_failure_returns_a_failed_maa_job(native_browser):
    controller, _ = native_browser
    controller._submit_browser(lambda: controller._current_page().route("**/blocked-navigation", lambda route: route.abort()))
    assert not controller.post_start_app("http://127.0.0.1/blocked-navigation").wait().succeeded
    assert controller.last_error
    assert controller.connected()


def test_owned_browser_can_reconnect_and_open_a_page_after_last_page_shutdown(monkeypatch, tmp_path, website):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    controller = BrowserController(
        f"http://127.0.0.1:{port}", browser_type="edge", executable_path=str(_EDGE),
        launch_args=["--headless=new", "about:blank"], name="owned-app-regression",
    )
    monkeypatch.setattr(controller, "_default_profile_dir", lambda _port: tmp_path / "browser-profile")
    try:
        assert controller.post_connection().wait().succeeded, controller.last_error
        process = controller.process
        assert controller.post_start_app(website).wait().succeeded, controller.last_error
        assert controller.post_stop_app("").wait().succeeded, controller.last_error
        assert process.poll() is not None
        assert controller.process is None
        assert controller._browser_thread is None
        assert controller.post_connection().wait().succeeded, controller.last_error
        assert controller.process.pid != process.pid
        assert controller.post_start_app(website).wait().succeeded, controller.last_error
    finally:
        controller._close_transport()
