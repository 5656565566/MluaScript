"""MluaScript TUI 应用入口"""

from __future__ import annotations

import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer

from mluascript.shared.logging import configure_logging, register_tui_sink

from .components.page import TopTabBar
from .screens.device import DevicesScreen
from .screens.home import HomeScreen
from .screens.logview import LogPage
from .screens.run import RunScreen
from .screens.template_run import TemplateRunScreen
from .screens.web import WebScreen


class TuiApp(App[None]):
    """MluaScript 控制界面"""

    exit_flag = 0
    force_exit_flag = 0
    TITLE = "MluaScript"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    .hidden {
        display: none;
    }
    .column {
        align: center top;
        & > * {
            max-width: 100;
        }
    }
    Screen .-maximized {
        margin: 1 2;
        max-width: 100%;
        &.column {
            margin: 1 2;
            padding: 1 2;
        }
        &.column > * {
            max-width: 100%;
        }
    }
    """

    BINDINGS = [
        Binding("ctrl+a", "maximize", "组件最大化", show=False),
        Binding("ctrl+c", "help_quit", show=False, system=True),
        Binding("ctrl+q", "help_force_quit", show=False),
    ]

    def on_mount(self) -> None:
        self.active_tab = "home"
        configure_logging(stdout=False)

    def compose(self) -> ComposeResult:
        yield TopTabBar()
        yield HomeScreen(id="home")
        yield DevicesScreen(id="devices", classes="hidden")
        yield RunScreen(id="run", classes="hidden")
        yield TemplateRunScreen(id="template-run", classes="hidden")
        yield LogPage(id="log", classes="hidden")
        yield WebScreen(id="web", classes="hidden")
        yield Footer()

    def action_switch_tab(self, mode: str) -> None:
        if hasattr(self, "active_tab") and mode == self.active_tab:
            return

        if hasattr(self, "active_tab") and self.active_tab:
            try:
                current_widget = self.query_one(f"#{self.active_tab}")
                current_widget.add_class("hidden")
            except Exception:
                pass

        try:
            new_widget = self.query_one(f"#{mode}")
            new_widget.remove_class("hidden")
        except Exception:
            pass

        self.active_tab = mode

        try:
            from textual.containers import Container
            for widget in self.query(Container):
                if widget.id == mode:
                    widget.can_focus = True
                    widget.focus()
        except Exception:
            pass

        try:
            tabs = self.query_one(TopTabBar)
            tabs.active = mode
        except Exception:
            pass

    def action_maximize(self) -> None:
        if self.screen.is_maximized:
            return

        if self.screen.focused is None:
            self.notify(
                "无需最大化 (尝试按 [b]tab[/b] 键)",
                title="组件最大化",
                severity="warning",
            )
            return

        if self.screen.maximize(self.screen.focused):
            self.notify(
                "全屏浏览页面中 按 [b]escape (Esc)[/b] 退出全屏",
                title="组件最大化",
            )
            return

        self.notify(
            "此部件可能未被最大化",
            title="组件最大化",
            severity="warning",
        )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "switch_tab" and parameters and getattr(self, "active_tab", None) == parameters[0]:
            return None
        return True

    def _has_running_tasks(self) -> bool:
        return False

    def _stop_background_tasks(self) -> int:
        return 0

    def _force_quit(self) -> None:
        stopped_units = self._stop_background_tasks()
        self.notify(
            f"已请求停止任务并关闭 MluaScript Web 控制台，共处理 {stopped_units} 个运行单元，正在退出",
            title="强制退出",
            severity="warning",
        )
        self.exit()

    async def action_quit(self) -> None:
        if self._has_running_tasks():
            self.notify(
                "当前仍有脚本或任务在运行。请先停止任务；如需强制退出，请按 Ctrl+Q。",
                title="拒绝直接退出",
                severity="warning",
            )
            return

        self.notify("正在安全退出 MluaScript", title="退出程序")
        self.exit()

    def action_help_quit(self) -> None:
        now = int(__import__("time").time())
        if (now - self.exit_flag) < 3:
            self.exit_flag = 0
            self.force_exit_flag = 0
            self.call_next(self.action_quit)
            return

        self.force_exit_flag = 0
        self.exit_flag = now
        has_running_tasks = self._has_running_tasks()
        message = (
            "再按一次 [b]Ctrl+C[/b] 正常退出\n"
            "若任务仍在运行，可按 [b]Ctrl+Q[/b] 准备强制退出"
            if has_running_tasks
            else "再按一次 [b]Ctrl+C[/b] 正常退出"
        )
        self.notify(
            message,
            title="确认退出",
            severity="warning" if has_running_tasks else "information",
            timeout=3,
        )

    def action_help_force_quit(self) -> None:
        now = int(__import__("time").time())
        if (now - self.force_exit_flag) < 3:
            self.force_exit_flag = 0
            self.exit_flag = 0
            self._force_quit()
            return

        self.exit_flag = 0
        self.force_exit_flag = now
        self.notify(
            "再按一次 [b]Ctrl+Q[/b] 将直接强制退出\n会请求停止任务并关闭 MluaScript Web",
            title="确认强制退出",
            severity="error",
            timeout=3,
        )
