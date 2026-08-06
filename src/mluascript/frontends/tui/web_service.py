"""由 Textual 应用托管的 Web 服务生命周期。"""

from __future__ import annotations

import asyncio
import logging
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

from textual.app import App
from textual.worker import Worker, WorkerCancelled, WorkerFailed, WorkerState, get_current_worker

from mluascript.frontends.web import EmbeddedUvicornServer, create_mluascript_web_server
from mluascript.shared.config import config as config_registry
from mluascript.shared.config import load_config
from mluascript.shared.config.models import GlobalConfig, WebServerConfig
from mluascript.shared.logging import LoguruHandler, logger


WebServiceStatus = Literal["stopped", "starting", "running", "stopping", "failed"]
WebServiceStatusListener = Callable[[WebServiceStatus], None]


class WebServerProtocol(Protocol):
    started: bool
    should_exit: bool
    force_exit: bool

    async def serve(self) -> None: ...

    async def shutdown(self) -> None: ...


WebServerFactory = Callable[[str, int], WebServerProtocol]


@dataclass(slots=True)
class _LoggerSnapshot:
    handlers: list[logging.Handler]
    level: int
    propagate: bool
    disabled: bool


class _UvicornErrorCaptureHandler(logging.Handler):
    """静默捕获 Uvicorn 错误，避免关闭 Web 日志后丢失启动失败原因。"""

    def __init__(self, on_error: Callable[[logging.LogRecord], None]) -> None:
        super().__init__(level=logging.ERROR)
        self._on_error = on_error

    def emit(self, record: logging.LogRecord) -> None:
        self._on_error(record)


class _UvicornLogBridge:
    """在 Web 生命周期内把 Uvicorn 标准日志定向到项目日志。"""

    def __init__(self, on_error: Callable[[logging.LogRecord], None]) -> None:
        self._on_error = on_error
        self._snapshots: dict[str, _LoggerSnapshot] = {}

    def install(self, *, enabled: bool) -> None:
        if self._snapshots:
            return

        if enabled:
            bindings: dict[str, logging.Handler] = {
                "uvicorn": LoguruHandler(source="web", channel="web.server", on_record=self._on_error),
                "uvicorn.error": LoguruHandler(source="web", channel="web.server", on_record=self._on_error),
                "uvicorn.access": LoguruHandler(source="web", channel="web.access"),
            }
        else:
            bindings = {
                "uvicorn": logging.NullHandler(),
                "uvicorn.error": _UvicornErrorCaptureHandler(self._on_error),
                "uvicorn.access": logging.NullHandler(),
            }
        for name, handler in bindings.items():
            target = logging.getLogger(name)
            self._snapshots[name] = _LoggerSnapshot(
                handlers=list(target.handlers),
                level=target.level,
                propagate=target.propagate,
                disabled=target.disabled,
            )
            target.handlers = [handler]
            target.setLevel(logging.INFO if enabled else logging.ERROR)
            target.propagate = False
            target.disabled = False

    def restore(self) -> None:
        for name, snapshot in self._snapshots.items():
            target = logging.getLogger(name)
            target.handlers = snapshot.handlers
            target.setLevel(snapshot.level)
            target.propagate = snapshot.propagate
            target.disabled = snapshot.disabled
        self._snapshots.clear()


class WebServiceController:
    """TUI 唯一持有的嵌入式 Web 服务控制器。"""

    def __init__(
        self,
        app: App[Any],
        *,
        server_factory: WebServerFactory = create_mluascript_web_server,
        web_logs_enabled: bool | None = None,
    ) -> None:
        self._app = app
        self._server_factory = server_factory
        self._web_logs_enabled = web_logs_enabled
        self._operation_lock = asyncio.Lock()
        self._server: WebServerProtocol | None = None
        self._worker: Worker[None] | None = None
        self._status: WebServiceStatus = "stopped"
        self._status_listeners: set[WebServiceStatusListener] = set()
        self._host = "127.0.0.1"
        self._port = 18080
        self._last_error = ""
        self._stop_requested = False
        self._log_bridge = _UvicornLogBridge(self._capture_uvicorn_error)

    @property
    def status(self) -> WebServiceStatus:
        return self._status

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def worker(self) -> Worker[None] | None:
        return self._worker

    def configured_host_port(self) -> tuple[str, int]:
        try:
            web_config = config_registry.get(WebServerConfig)
        except RuntimeError:
            load_config()
            web_config = config_registry.get(WebServerConfig)
        return web_config.host, web_config.port

    def _should_enable_web_logs(self) -> bool:
        if self._web_logs_enabled is not None:
            return self._web_logs_enabled
        return str(config_registry.get(GlobalConfig).log_level).upper() == "DEBUG"

    def subscribe(self, listener: WebServiceStatusListener) -> Callable[[], None]:
        """订阅生命周期状态变化，并立即同步当前状态。"""

        self._status_listeners.add(listener)
        listener(self._status)
        return lambda: self._status_listeners.discard(listener)

    def _set_status(self, status: WebServiceStatus) -> None:
        if self._status == status:
            return
        self._status = status
        for listener in tuple(self._status_listeners):
            try:
                listener(status)
            except Exception as exc:
                # 状态观察者不能中断 Web 生命周期操作。
                if self._should_enable_web_logs():
                    logger.bind(source="web", channel="web.server").warning(f"Web 状态观察者异常: {exc}")

    def _capture_uvicorn_error(self, record: logging.LogRecord) -> None:
        # Uvicorn 常在具体异常后再输出通用 startup failed，保留第一条根因信息。
        if record.levelno >= logging.ERROR and not self._last_error:
            self._last_error = record.getMessage()

    async def _serve(self, server: WebServerProtocol) -> None:
        cancelled = False
        try:
            await server.serve()
        except asyncio.CancelledError:
            cancelled = True
            server.should_exit = True
            try:
                await asyncio.wait_for(asyncio.shield(server.shutdown()), timeout=2.0)
            except (Exception, asyncio.CancelledError):
                server.force_exit = True
            raise
        except SystemExit as exc:
            if not self._last_error:
                self._last_error = f"Web 服务启动失败，退出码 {exc.code}"
        except Exception as exc:
            self._last_error = self._last_error or str(exc) or exc.__class__.__name__
            if self._should_enable_web_logs():
                logger.bind(source="web", channel="web.server").exception(f"MluaScript Web 服务异常退出: {exc}")
        finally:
            try:
                # Uvicorn 在线程 Worker 内运行，所有 Textual 状态更新必须回到应用线程。
                self._app.call_from_thread(self._finish_server, server, cancelled)
            except Exception:
                # 应用异常退出时可能已无法调度回主线程，日志桥仍必须恢复。
                if self._server is server:
                    self._server = None
                    self._log_bridge.restore()

    def _finish_server(self, server: WebServerProtocol, cancelled: bool) -> None:
        if self._server is not server:
            return
        if cancelled or self._status not in {"failed", "stopping"}:
            self._set_status("stopped")
        self._server = None
        self._log_bridge.restore()

    def _serve_in_thread(self, server: WebServerProtocol) -> None:
        """在 Textual 管理的线程 Worker 内运行独立的 Uvicorn 事件循环。"""

        worker = get_current_worker()

        async def supervise() -> None:
            serve_task = asyncio.create_task(self._serve(server))
            shutdown_requested = False
            while not serve_task.done():
                if worker.is_cancelled and not shutdown_requested:
                    shutdown_requested = True
                    server.should_exit = True
                    try:
                        await asyncio.wait_for(server.shutdown(), timeout=2.0)
                    except Exception:
                        server.force_exit = True
                await asyncio.sleep(0.05)
            await serve_task

        asyncio.run(supervise())

    async def start(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        startup_timeout: float = 5.0,
    ) -> str:
        async with self._operation_lock:
            if self._status == "running":
                return self.url
            if self._status == "stopping":
                raise RuntimeError("MluaScript Web 正在关闭，请稍后重试")

            configured_host, configured_port = self.configured_host_port()
            self._host = host or configured_host
            self._port = port or configured_port
            self._last_error = ""
            self._stop_requested = False
            self._set_status("starting")
            self._log_bridge.install(enabled=self._should_enable_web_logs())

            try:
                server = self._server_factory(self._host, self._port)
            except Exception as exc:
                self._last_error = str(exc) or exc.__class__.__name__
                self._set_status("failed")
                self._log_bridge.restore()
                raise

            self._server = server
            self._worker = self._app.run_worker(
                lambda: self._serve_in_thread(server),
                name="mluascript-web-server",
                group="web-service",
                exit_on_error=False,
                exclusive=True,
                thread=True,
            )

            deadline = asyncio.get_running_loop().time() + startup_timeout
            while asyncio.get_running_loop().time() < deadline:
                if self._stop_requested:
                    self._set_status("stopping")
                    server.should_exit = True
                    await self._wait_for_worker(timeout=1.0, cancel_on_timeout=True)
                    self._set_status("stopped")
                    raise RuntimeError("MluaScript Web 启动已取消")
                if server.started:
                    self._set_status("running")
                    if self._should_enable_web_logs():
                        logger.bind(source="web", channel="web.server").info(f"MluaScript Web 启动于 {self.url}")
                    return self.url
                if self._worker.state in {WorkerState.ERROR, WorkerState.CANCELLED, WorkerState.SUCCESS}:
                    break
                await asyncio.sleep(0.05)

            if self._worker.state == WorkerState.ERROR and self._worker.error is not None:
                self._last_error = self._last_error or str(self._worker.error)
            if not self._last_error:
                self._last_error = "MluaScript Web 启动超时" if self._worker.is_running else "MluaScript Web 启动失败"
            self._set_status("failed")
            server.should_exit = True
            await self._wait_for_worker(timeout=1.0, cancel_on_timeout=True)
            raise RuntimeError(self._last_error)

    async def _wait_for_worker(self, *, timeout: float, cancel_on_timeout: bool) -> bool:
        worker = self._worker
        if worker is None:
            return True
        try:
            await asyncio.wait_for(worker.wait(), timeout=timeout)
        except (WorkerCancelled, WorkerFailed):
            pass
        except TimeoutError:
            if cancel_on_timeout:
                worker.cancel()
            return False
        return not worker.is_running

    async def stop(self, *, timeout: float = 5.0, cancel_on_timeout: bool = True) -> bool:
        # 先发停止信号，避免等待正在执行启动检查的串行操作结束后才取消服务。
        self._stop_requested = True
        if self._server is not None:
            self._server.should_exit = True
        async with self._operation_lock:
            server = self._server
            worker = self._worker
            if server is None or worker is None or not worker.is_running:
                self._set_status("stopped")
                self._server = None
                self._log_bridge.restore()
                self._stop_requested = False
                return True

            self._set_status("stopping")
            server.should_exit = True
            stopped = await self._wait_for_worker(timeout=timeout, cancel_on_timeout=cancel_on_timeout)
            if stopped:
                self._set_status("stopped")
                self._stop_requested = False
                if self._should_enable_web_logs():
                    logger.bind(source="web", channel="web.server").info("MluaScript Web 已停止")
            else:
                self._last_error = "MluaScript Web 未能在超时时间内关闭"
                if self._should_enable_web_logs():
                    logger.bind(source="web", channel="web.server").warning(self._last_error)
            return stopped

    async def open(self, host: str | None = None, port: int | None = None) -> str:
        if self._status != "running":
            await self.start(host, port)
        await asyncio.to_thread(webbrowser.open, self.url)
        return self.url


__all__ = ["WebServiceController", "WebServiceStatus", "WebServiceStatusListener"]
