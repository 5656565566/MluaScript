"""TUI Web 控制页面"""

from __future__ import annotations

import time
import webbrowser

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Input, Static

from mluascript.frontends.web import (
    get_mluascript_web_host_port,
    get_mluascript_web_url,
    is_mluascript_web_running,
    run_mluascript_web_server_in_thread,
    stop_mluascript_web_server,
)


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
        host, port = get_mluascript_web_host_port()
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
        default_host, default_port = get_mluascript_web_host_port()
        status = self.query_one("#web-status", Static)
        url_widget = self.query_one("#web-url", Static)
        if is_mluascript_web_running():
            status.update("[green]Web 运行中[/green]")
            url_widget.update(f"[cyan]{get_mluascript_web_url()}[/cyan]")
        else:
            status.update("[yellow]Web 未启动[/yellow]")
            url_widget.update(f"[dim]默认地址: http://{default_host}:{default_port}[/dim]")

    def action_refresh_status(self) -> None:
        self._refresh_status()
        self.notify("已刷新 Web 状态")

    @work(thread=True)
    def action_toggle_web(self) -> None:
        runtime = self._get_runtime_host_port()
        if runtime is None:
            return
        host, port = runtime
        if is_mluascript_web_running():
            ok = stop_mluascript_web_server()
            if ok:
                self.app.call_from_thread(self.notify, "Web 已关闭", title="Web")
            else:
                self.app.call_from_thread(self.notify, "Web 关闭超时", title="Web", severity="error")
            self.app.call_from_thread(self._refresh_status)
            return

        url = run_mluascript_web_server_in_thread(host, port)
        self.app.call_from_thread(self.notify, f"Web 已启动: {url}", title="MluaScript Web")
        self.app.call_from_thread(self._refresh_status)

    @work(thread=True)
    def action_open_web(self) -> None:
        runtime = self._get_runtime_host_port()
        if runtime is None:
            return
        host, port = runtime
        if not is_mluascript_web_running():
            run_mluascript_web_server_in_thread(host, port)
            time.sleep(0.5)
        url = get_mluascript_web_url()
        webbrowser.open(url)
        self.app.call_from_thread(self.notify, f"已打开 {url}", title="Web")
        self.app.call_from_thread(self._refresh_status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle-web":
            self.action_toggle_web()
        elif event.button.id == "btn-open-web":
            self.action_open_web()
