"""MluaScript 日志页面"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import RichLog

from mluascript.shared.logging import (
    logger,
    bind_tui_log_target,
    build_log_lines,
    clear_log_buffers,
    get_logs,
    register_tui_sink,
)


class LogPage(Container):
    """显示日志内容的页面"""

    DEFAULT_CSS = """
    LogPage {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    #log-viewer {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding(
            "c",
            "clear_log",
            "清空全部日志",
            tooltip="清空全局日志和脚本日志",
        ),
        Binding(
            "ctrl+a",
            "app.maximize",
            "组件最大化",
            tooltip="组件全屏（如果页面支持）",
            show=False,
        ),
    ]

    def compose(self) -> ComposeResult:
        self.viewer = RichLog(id="log-viewer", markup=False, wrap=True, auto_scroll=True, max_lines=200)
        yield self.viewer

    def on_mount(self) -> None:
        self._sync_history()
        register_tui_sink(self.viewer)

    def on_show(self) -> None:
        self._sync_history()
        bind_tui_log_target(self.viewer)

    def _sync_history(self) -> None:

        if not self.viewer.is_attached:
            return

        self.viewer.clear()
        items = get_logs()
        for line in build_log_lines(items):
            self.viewer.write(Text.from_ansi(line))

    def action_clear_log(self) -> None:
        clear_log_buffers()
        self.viewer.clear()
        self.notify("已清空日志缓冲")
