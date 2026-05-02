"""设备管理页面"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer, Vertical
from textual.widgets import Button, Input, Markdown, Static, TabbedContent, TabPane

from mluascript.control.devices import DeviceOverview, DevicePage
from mluascript.control.facade import get_control_facade

MAX_VISIBLE_DEVICE_ITEMS = 8


class DevicesScreen(Container):
    DEFAULT_CSS = """
    DevicesScreen {
        width: 100%;
        height: 1fr;
        overflow-y: hidden;
    }

    .device-btn {
        margin: 1;
        width: 100%;
    }

    .device-btn-green {
        background: #4CAF50;
        margin: 1;
        width: 100%;
    }

    .device-btn-blue {
        background: #2196F3;
        margin: 1;
        width: 100%;
    }

    .device-btn-orange {
        background: #FF9800;
        margin: 1;
        width: 100%;
    }

    .device-btn-purple {
        background: #9C27B0;
        margin: 1;
        width: 100%;
    }

    .adb-input {
        margin: 1;
        width: 100%;
    }

    .device-summary {
        margin: 0 1 1 1;
        color: $text-muted;
    }

    .device-results {
        height: auto;
        width: 100%;
    }

    .tab-scroll-area {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("r", "refresh_devices", "刷新", tooltip="刷新设备连接状态"),
    ]

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("ADB设备"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("[dim]当前未连接设备[/dim]", id="conn-status")

                    yield Static("[dim]尚未搜索 ADB 设备[/dim]", id="adb-summary", classes="device-summary")
                    yield Static("[dim]使用分页浏览搜索结果[/dim]", id="adb-page-info", classes="device-summary")
                    yield Button("ADB 上一页", id="btn-adb-prev", classes="device-btn", disabled=True)
                    yield Button("ADB 下一页", id="btn-adb-next", classes="device-btn", disabled=True)
                    with Vertical(id="adb-list-container", classes="device-results"):
                        for i in range(MAX_VISIBLE_DEVICE_ITEMS):
                            btn = Button("", classes="device-btn-blue", id=f"btn-adb-{i}", disabled=True)
                            btn.display = False
                            yield btn

                    yield Button("搜索 ADB 设备", classes="device-btn-blue", id="btn-find-adb")

                    yield Static("[dim]手动输入 ADB 地址:[/dim]")
                    yield Input(placeholder="127.0.0.1:5555", id="adb-address", classes="adb-input")
                    yield Button("连接 ADB", classes="device-btn-green", id="btn-connect-adb")

            with TabPane("模拟器设备"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("[dim]配置的模拟器设备[/dim]", id="emulator-summary", classes="device-summary")
                    with Vertical(id="emulator-list-container", classes="device-results"):
                        for i in range(MAX_VISIBLE_DEVICE_ITEMS):
                            btn = Button("", classes="device-btn-purple", id=f"btn-emulator-{i}", disabled=True)
                            btn.display = False
                            yield btn

            with TabPane("浏览器设备"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("[dim]配置的浏览器设备[/dim]", id="browser-summary", classes="device-summary")
                    with Vertical(id="browser-list-container", classes="device-results"):
                        for i in range(MAX_VISIBLE_DEVICE_ITEMS):
                            btn = Button("", classes="device-btn-purple", id=f"btn-browser-{i}", disabled=True)
                            btn.display = False
                            yield btn

            with TabPane("Win32窗口"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("[dim]尚未搜索 Win32 窗口[/dim]", id="win32-summary", classes="device-summary")
                    yield Static("[dim]使用分页浏览搜索结果[/dim]", id="win32-page-info", classes="device-summary")
                    yield Button("Win32 上一页", id="btn-win32-prev", classes="device-btn", disabled=True)
                    yield Button("Win32 下一页", id="btn-win32-next", classes="device-btn", disabled=True)
                    with Vertical(id="win32-list-container", classes="device-results"):
                        for i in range(MAX_VISIBLE_DEVICE_ITEMS):
                            btn = Button("", classes="device-btn-blue", id=f"btn-win32-{i}", disabled=True)
                            btn.display = False
                            yield btn

                    yield Button("搜索 Win32 窗口", classes="device-btn-blue", id="btn-find-win32")

            with TabPane("已连接设备"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Markdown("### 截图测试")
                    yield Static("点击按钮即可对当前已连接设备截图", classes="device-summary")
                    yield Static("TUI 会将截图保存到 ./temp 目录下", classes="device-summary")
                    yield Button("当前无已连接的设备", classes="device-btn-orange", disabled=True, id="btn-screencap")

            with TabPane("管理"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("[dim]MAA 控制器未初始化[/dim]", id="init-status")
                    yield Button("初始化 MAA 控制器", classes="device-btn-green", id="btn-init")

    @property
    def _control(self):
        return get_control_facade()

    def on_mount(self) -> None:
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        overview = self._control.get_device_overview()
        self._apply_overview(overview)

    def _apply_overview(self, overview: DeviceOverview) -> None:
        self.query_one("#init-status", Static).update(
            "[green]MAA 控制器已初始化[/green]" if overview.connection.initialized else "[dim]MAA 控制器未初始化[/dim]"
        )
        self.query_one("#conn-status", Static).update(
            f"[green]当前连接: {overview.connection.label}[/green]" if overview.connection.label else "[dim]当前未连接设备[/dim]"
        )
        screencap_button = self.query_one("#btn-screencap", Button)
        screencap_button.label = overview.connection.screencap_label
        screencap_button.disabled = not overview.connection.can_screencap

        self._apply_page(
            page=overview.adb,
            summary_id="#adb-summary",
            page_info_id="#adb-page-info",
            prev_id="#btn-adb-prev",
            next_id="#btn-adb-next",
            prefix="btn-adb-",
            label_builder=lambda item: item.title if not item.subtitle else f"{item.title} | {item.subtitle}",
        )
        self._apply_page(
            page=overview.win32,
            summary_id="#win32-summary",
            page_info_id="#win32-page-info",
            prev_id="#btn-win32-prev",
            next_id="#btn-win32-next",
            prefix="btn-win32-",
            label_builder=lambda item: item.title if not item.subtitle else f"{item.title} | {item.subtitle}",
        )
        self._apply_page(
            page=overview.emulator,
            summary_id="#emulator-summary",
            page_info_id=None,
            prev_id=None,
            next_id=None,
            prefix="btn-emulator-",
            label_builder=lambda item: item.title if not item.subtitle else f"{item.title} | {item.subtitle}",
        )
        self._apply_page(
            page=overview.browser,
            summary_id="#browser-summary",
            page_info_id=None,
            prev_id=None,
            next_id=None,
            prefix="btn-browser-",
            label_builder=lambda item: item.title if not item.subtitle else f"{item.title} | {item.subtitle}",
        )

    def _apply_page(
        self,
        *,
        page: DevicePage,
        summary_id: str,
        page_info_id: str | None,
        prev_id: str | None,
        next_id: str | None,
        prefix: str,
        label_builder,
    ) -> None:
        self.query_one(summary_id, Static).update(f"[dim]{page.summary}[/dim]" if page.total == 0 else f"[green]{page.summary}[/green]")
        if page_info_id is not None:
            info = "[dim]无结果[/dim]" if page.total == 0 else f"[dim]第 {page.page_index + 1}/{page.page_count} 页，共 {page.total} 项[/dim]"
            self.query_one(page_info_id, Static).update(info)
        if prev_id is not None:
            self.query_one(prev_id, Button).disabled = not page.has_prev
        if next_id is not None:
            self.query_one(next_id, Button).disabled = not page.has_next

        for i in range(MAX_VISIBLE_DEVICE_ITEMS):
            button = self.query_one(f"#{prefix}{i}", Button)
            if i < len(page.items):
                item = page.items[i]
                button.label = label_builder(item)
                button.disabled = not item.enabled
                button.display = True
            else:
                button.label = ""
                button.disabled = True
                button.display = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if not btn_id:
            return

        if btn_id == "btn-init":
            self._do_init()
        elif btn_id == "btn-find-adb":
            self._do_find_adb()
        elif btn_id == "btn-connect-adb":
            self._do_connect_adb()
        elif btn_id == "btn-find-win32":
            self._do_find_win32()
        elif btn_id == "btn-screencap":
            self._do_screencap()
        elif btn_id == "btn-adb-prev":
            self._apply_overview(self._control.change_adb_page(-1))
        elif btn_id == "btn-adb-next":
            self._apply_overview(self._control.change_adb_page(1))
        elif btn_id == "btn-win32-prev":
            self._apply_overview(self._control.change_win32_page(-1))
        elif btn_id == "btn-win32-next":
            self._apply_overview(self._control.change_win32_page(1))
        elif btn_id.startswith("btn-adb-"):
            idx = int(btn_id.split("-")[-1])
            overview = self._control.get_device_overview()
            if idx < len(overview.adb.items):
                self._do_connect_device(overview.adb.items[idx].id)
        elif btn_id.startswith("btn-win32-"):
            idx = int(btn_id.split("-")[-1])
            overview = self._control.get_device_overview()
            if idx < len(overview.win32.items):
                self._do_connect_device(overview.win32.items[idx].id) 
        elif btn_id.startswith("btn-emulator-"):
            idx = int(btn_id.split("-")[-1])
            overview = self._control.get_device_overview()
            if idx < len(overview.emulator.items):
                self._do_connect_device(overview.emulator.items[idx].id)
        elif btn_id.startswith("btn-browser-"):
            idx = int(btn_id.split("-")[-1])
            overview = self._control.get_device_overview()
            if idx < len(overview.browser.items):
                self._do_connect_device(overview.browser.items[idx].id)

    def action_refresh_devices(self) -> None:
        self._refresh_ui()
        self.notify("已刷新设备状态")

    def _handle_action_result(self, result) -> None:
        if result.overview is not None:
            self.app.call_from_thread(self._apply_overview, result.overview)
        self.app.call_from_thread(self.notify, result.message, severity=result.severity)

    @work(thread=True)
    def _do_init(self) -> None:
        result = self._control.initialize_devices()
        self._handle_action_result(result)

    @work(thread=True)
    def _do_find_adb(self) -> None:
        result = self._control.find_adb_devices()
        self._handle_action_result(result)

    @work(thread=True)
    def _do_connect_adb(self) -> None:
        address = self.query_one("#adb-address", Input).value.strip()
        result = self._control.connect_adb(address)
        self._handle_action_result(result)

    @work(thread=True)
    def _do_find_win32(self) -> None:
        result = self._control.find_win32_windows()
        self._handle_action_result(result)

    @work(thread=True)
    def _do_screencap(self) -> None:
        result = self._control.screencap_current_device_and_save()
        self._handle_action_result(result)

    @work(thread=True)
    def _do_connect_device(self, device_id: str) -> None:
        result = self._control.connect_device(device_id)
        self._handle_action_result(result)