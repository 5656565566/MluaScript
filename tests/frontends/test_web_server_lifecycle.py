from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import socket
import urllib.request

import pytest
from textual.app import App
from textual.worker import WorkerCancelled

import mluascript.frontends.web.server as web_server
import mluascript.frontends.tui.web_service as tui_web_service
from mluascript.frontends.tui.web_service import WebServiceController
from mluascript.shared.config.models import GlobalConfig
from mluascript.shared.logging import clear_log_buffers, configure_logging, get_logs_by_channel, logger
from mluascript.shared.logging.logger import tui_filter


class _FakeServer:
    def __init__(self, *, fail_message: str = "") -> None:
        self.started = False
        self.should_exit = False
        self.force_exit = False
        self.fail_message = fail_message
        self.shutdown_called = False

    async def serve(self) -> None:
        if self.fail_message:
            logging.getLogger("uvicorn.error").error(self.fail_message)
            logging.getLogger("uvicorn.error").error("Application startup failed. Exiting.")
            raise SystemExit(3)
        self.started = True
        logging.getLogger("uvicorn.error").info("server ready")
        logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET / HTTP/1.1" 200')
        while not self.should_exit:
            await asyncio.sleep(0.005)

    async def shutdown(self) -> None:
        self.shutdown_called = True
        self.should_exit = True


def test_tui_log_filter_excludes_only_web_access_channel() -> None:
    info_level = logger.level("INFO")

    assert tui_filter({"level": info_level, "extra": {"channel": "web.access"}}) is False
    assert tui_filter({"level": info_level, "extra": {"channel": "web.server"}}) is True
    assert tui_filter({"level": info_level, "extra": {"channel": "runtime.log"}}) is True


def test_web_logs_follow_global_debug_level(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = WebServiceController(App())

    monkeypatch.setattr(tui_web_service.config_registry, "get", lambda _model: GlobalConfig(log_level="DEBUG"))
    assert controller._should_enable_web_logs() is True

    monkeypatch.setattr(tui_web_service.config_registry, "get", lambda _model: GlobalConfig(log_level="INFO"))
    assert controller._should_enable_web_logs() is False


def test_web_server_factory_disables_uvicorn_logging_and_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    app = object()
    monkeypatch.setattr(web_server, "create_web_app", lambda _dist_dir: app)

    server = web_server.create_mluascript_web_server("127.0.0.1", 19080)

    assert isinstance(server, web_server.EmbeddedUvicornServer)
    assert server.config.app is app
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 19080
    assert server.config.log_config is None
    with server.capture_signals():
        pass


def test_tui_controller_owns_start_stop_and_uvicorn_logs() -> None:
    async def scenario() -> None:
        created: list[_FakeServer] = []

        def factory(_host: str, _port: int) -> _FakeServer:
            server = _FakeServer()
            created.append(server)
            return server

        app = App()
        async with app.run_test():
            controller = WebServiceController(app, server_factory=factory, web_logs_enabled=True)
            statuses: list[str] = []
            unsubscribe = controller.subscribe(statuses.append)
            url = await controller.start("127.0.0.1", 19080, startup_timeout=0.5)

            assert url == "http://127.0.0.1:19080"
            assert controller.status == "running"
            assert controller.worker is not None and controller.worker.is_running
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
                assert not any(isinstance(handler, logging.StreamHandler) for handler in logging.getLogger(name).handlers)

            assert await controller.stop(timeout=0.5) is True
            assert controller.status == "stopped"
            assert created[0].should_exit is True
            assert statuses == ["stopped", "starting", "running", "stopping", "stopped"]

            unsubscribe()

    configure_logging(stdout=False)
    clear_log_buffers()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        asyncio.run(scenario())

    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    assert any(item["message"] == "server ready" for item in get_logs_by_channel("web.server"))
    assert any("GET / HTTP/1.1" in item["message"] for item in get_logs_by_channel("web.access"))


def test_tui_controller_suppresses_web_logs_when_debug_is_disabled() -> None:
    async def scenario() -> None:
        app = App()
        async with app.run_test():
            controller = WebServiceController(
                app,
                server_factory=lambda _host, _port: _FakeServer(),
                web_logs_enabled=False,
            )
            await controller.start("127.0.0.1", 19080, startup_timeout=0.5)
            assert await controller.stop(timeout=0.5) is True

    configure_logging(stdout=False)
    clear_log_buffers()
    asyncio.run(scenario())

    assert get_logs_by_channel("web.server") == []
    assert get_logs_by_channel("web.access") == []


def test_tui_controller_preserves_uvicorn_startup_error() -> None:
    async def scenario() -> None:
        app = App()
        async with app.run_test():
            controller = WebServiceController(
                app,
                server_factory=lambda _host, _port: _FakeServer(fail_message="bind failed: address already in use"),
            )
            with pytest.raises(RuntimeError, match="address already in use"):
                await controller.start("127.0.0.1", 19080, startup_timeout=0.5)
            assert controller.status == "failed"
            assert controller.last_error == "bind failed: address already in use"

    configure_logging(stdout=False)
    asyncio.run(scenario())


def test_textual_worker_cancellation_runs_web_shutdown_fallback() -> None:
    async def scenario() -> None:
        server = _FakeServer()
        app = App()
        async with app.run_test():
            controller = WebServiceController(app, server_factory=lambda _host, _port: server)
            await controller.start("127.0.0.1", 19080, startup_timeout=0.5)
            worker = controller.worker
            assert worker is not None

            worker.cancel()
            with pytest.raises(WorkerCancelled):
                await worker.wait()

            # 线程 Worker 的取消标记由监督协程接收，再请求 Uvicorn 正常关闭。
            for _ in range(100):
                if server.shutdown_called and controller.status == "stopped":
                    break
                await asyncio.sleep(0.01)

            assert server.shutdown_called is True
            assert controller.status == "stopped"

    configure_logging(stdout=False)
    asyncio.run(scenario())


def test_real_uvicorn_runs_inside_textual_worker_without_terminal_output() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    async def scenario() -> None:
        app = App()
        async with app.run_test():
            controller = WebServiceController(app)
            url = await controller.start("127.0.0.1", port, startup_timeout=5.0)
            response = await asyncio.to_thread(urllib.request.urlopen, f"{url}/", timeout=3.0)
            try:
                assert response.status == 200
            finally:
                response.close()
            assert await controller.stop(timeout=5.0) is True
            assert controller.status == "stopped"

    configure_logging(stdout=False)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        asyncio.run(scenario())

    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
