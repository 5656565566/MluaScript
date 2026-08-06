"""TUI Web 控制页面"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Static


class WebScreen(Container):
    DEFAULT_CSS = """
    WebScreen {
        width: 100%;
        height: 1fr;
    }

    #web-shell {
        align: center top;
        padding: 1 2;
    }

    #web-card {
        width: 1fr;
        max-width: 72;
        min-height: 24;
        border: round $primary;
        padding: 1 2;
    }

    #web-button-row {
        width: 100%;
        height: auto;
        margin-top: 1;
    }

    .web-btn {
        width: 1fr;
        min-width: 16;
        margin: 0 1 0 0;
    }

    .web-btn:last-child {
        margin-right: 0;
    }

    .web-input {
        width: 100%;
        margin-top: 1;
    }

    .web-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        host, port = self.app.web_service.configured_host_port()
        with Vertical(id="web-shell"):
            with Vertical(id="web-card"):
                yield Static("", id="web-status")
                yield Static("", id="web-url")
                yield Static("监听地址", classes="web-hint")
                yield Input(value=host, id="web-host-input", classes="web-input", placeholder="127.0.0.1")
                yield Static("监听端口", classes="web-hint")
                yield Input(value=str(port), id="web-port-input", classes="web-input", placeholder="18080")
                with Horizontal(id="web-button-row"):
                    yield Button("启动 / 关闭 Web", id="btn-toggle-web", classes="web-btn")
                    yield Button("打开 Web", id="btn-open-web", classes="web-btn")

    def on_mount(self) -> None:
        self._web_operation_active = False
        self._status_refresh_pending = False
        self._unsubscribe_web_service = self.app.web_service.subscribe(self._on_web_service_status_changed)

    def on_unmount(self) -> None:
        self._unsubscribe_web_service()

    def _on_web_service_status_changed(self, _status: str) -> None:
        if self.is_attached:
            self._refresh_status()

    def _get_runtime_host_port(self) -> tuple[str, int] | None:
        host_text = self.query_one("#web-host-input", Input).value.strip()
        port_text = self.query_one("#web-port-input", Input).value.strip()
        host = host_text or "127.0.0.1"
        try:
            port = int(port_text)
        except ValueError:
            self.notify("端口必须是整数", title="Web", severity="error")
            return None
        if port < 1 or port > 65535:
            self.notify("端口必须在 1-65535 之间", title="Web", severity="error")
            return None
        return host, port

    def _refresh_status(self) -> None:
        controller = self.app.web_service
        default_host, default_port = controller.configured_host_port()
        status = self.query_one("#web-status", Static)
        url_widget = self.query_one("#web-url", Static)
        toggle_button = self.query_one("#btn-toggle-web", Button)
        runtime_status = controller.status
        if runtime_status == "running":
            status.update("[green]Web 运行中[/green]")
            url_widget.update(f"[cyan]{controller.url}[/cyan]")
            toggle_button.label = "关闭 Web"
        elif runtime_status == "starting":
            status.update("[cyan]Web 正在启动[/cyan]")
            url_widget.update(f"[dim]{controller.url}[/dim]")
            toggle_button.label = "取消启动"
        elif runtime_status == "stopping":
            status.update("[yellow]Web 正在关闭[/yellow]")
            url_widget.update(f"[dim]{controller.url}[/dim]")
            toggle_button.label = "正在关闭"
            if not self._status_refresh_pending:
                self._status_refresh_pending = True
                self.set_timer(0.25, self._refresh_stopping_status)
        elif runtime_status == "failed":
            status.update("[red]Web 启动失败[/red]")
            url_widget.update(f"[red]{controller.last_error or '未知错误'}[/red]")
            toggle_button.label = "重试启动"
        else:
            status.update("[yellow]Web 未启动[/yellow]")
            url_widget.update(f"[dim]默认地址: http://{default_host}:{default_port}[/dim]")
            toggle_button.label = "启动 Web"
        toggle_button.disabled = self._web_operation_active or runtime_status == "stopping"
        self.query_one("#btn-open-web", Button).disabled = self._web_operation_active or runtime_status == "stopping"

    def _refresh_stopping_status(self) -> None:
        self._status_refresh_pending = False
        self._refresh_status()

    def _set_operation_active(self, active: bool) -> None:
        self._web_operation_active = active
        self._refresh_status()

    def action_refresh_status(self) -> None:
        self._refresh_status()
        self.notify("已刷新 Web 状态")

    def action_toggle_web(self) -> None:
        if self._web_operation_active:
            return
        controller = self.app.web_service
        if controller.status == "stopping":
            self.notify("Web 正在关闭，请稍候", title="Web", severity="warning")
            return
        if controller.status in {"running", "starting"}:
            self._set_operation_active(True)
            self._toggle_web_worker(None, None, True)
            return
        runtime = self._get_runtime_host_port()
        if runtime is None:
            return
        self._set_operation_active(True)
        self._toggle_web_worker(runtime[0], runtime[1], False)

    @work(group="web-screen-operation", exclusive=True, exit_on_error=False)
    async def _toggle_web_worker(self, host: str | None, port: int | None, should_stop: bool) -> None:
        try:
            if should_stop:
                stopped = await self.app.web_service.stop()
                if stopped:
                    self.notify("Web 已关闭", title="Web")
                else:
                    self.notify("Web 关闭超时", title="Web", severity="error")
                return

            url = await self.app.web_service.start(host, port)
            self.notify(f"Web 已启动: {url}", title="MluaScript Web")
        except Exception as exc:
            self.notify(str(exc), title="Web 操作失败", severity="error")
        finally:
            self._set_operation_active(False)

    def action_open_web(self) -> None:
        if self._web_operation_active:
            return
        controller = self.app.web_service
        if controller.status == "stopping":
            self.notify("Web 正在关闭，请稍候", title="Web", severity="warning")
            return
        host: str | None = None
        port: int | None = None
        if controller.status != "running":
            runtime = self._get_runtime_host_port()
            if runtime is None:
                return
            host, port = runtime
        self._set_operation_active(True)
        self._open_web_worker(host, port)

    @work(group="web-screen-operation", exclusive=True, exit_on_error=False)
    async def _open_web_worker(self, host: str | None, port: int | None) -> None:
        try:
            url = await self.app.web_service.open(host, port)
            self.notify(f"已打开 {url}", title="Web")
        except Exception as exc:
            self.notify(str(exc), title="打开 Web 失败", severity="error")
        finally:
            self._set_operation_active(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle-web":
            self.action_toggle_web()
        elif event.button.id == "btn-open-web":
            self.action_open_web()
