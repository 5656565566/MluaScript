"""TUI 通用页面组件"""

from __future__ import annotations

from typing import cast, TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.widgets import Tabs, Tab

if TYPE_CHECKING:
    from ..__init__ import TuiApp


class TopTabBar(Tabs):
    """全局顶部标签页栏"""

    DEFAULT_CSS = """
    TopTabBar {
        dock: top;
        width: 100%;
        background: $panel;
    }
    """

    def on_mount(self) -> None:
        self.add_tab(Tab("主页", id="home"))
        self.add_tab(Tab("设备管理", id="devices"))
        self.add_tab(Tab("运行任务", id="run"))
        self.add_tab(Tab("模板执行", id="template-run"))
        self.add_tab(Tab("日志", id="log"))
        self.add_tab(Tab("Web", id="web"))

        def set_active_tab():
            active_tab = getattr(self.tui_app, "active_tab", None)
            if active_tab:
                self.active = active_tab

        self.call_later(set_active_tab)

    @property
    def tui_app(self) -> "TuiApp":
        return cast("TuiApp", self.app)

    @on(Tabs.TabActivated)
    def handle_tab_activated(self, event: Tabs.TabActivated) -> None:
        """监听标签页被点击或被键盘触发的事件"""
        target_mode = event.tab.id

        if target_mode and getattr(self.tui_app, "active_tab", None) != target_mode:
            self.tui_app.action_switch_tab(target_mode)
