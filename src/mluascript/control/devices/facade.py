from __future__ import annotations

import numpy as np
import io
import time
import base64
from math import ceil
from pathlib import Path
from PIL import Image

from mluascript.maa import MaaFacade
from mluascript.maa.config import MaaDeviceConfig
from mluascript.maa.connections import (
    AdbConnectionParams,
    Win32ConnectionParams,
    connect_adb,
    connect_browser,
    connect_win32,
    find_adb_devices,
    find_desktop_windows,
)
from mluascript.maa.controllers.screen import screencap
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaPaths
from mluascript.shared.config import GlobalConfig, config, load_config

from .models import (
    ConnectAdbRequest,
    DeviceActionResult,
    DeviceConnectionState,
    DeviceListItem,
    DeviceOverview,
    DevicePage,
)

PAGE_SIZE = 8


class DeviceFacade:
    """设备域高层入口，向 frontends 提供通用应用层模型。"""

    def __init__(self) -> None:
        self._maa_facade = MaaFacade(
            MaaContext(
                paths=MaaPaths(
                    library_dir=Path("."),
                    resource_dir=Path("."),
                )
            )
        )
        self._adb_raw: list[dict] = []
        self._win32_raw: list[dict] = []
        self._adb_page = 0
        self._win32_page = 0

    def get_overview(self) -> DeviceOverview:
        return DeviceOverview(
            adb=self._build_adb_page(),
            win32=self._build_win32_page(),
            emulator=self._build_emulator_page(),
            browser=self._build_browser_page(),
            connection=self._build_connection_state(),
        )

    def initialize(self) -> DeviceActionResult:
        return DeviceActionResult(ok=True, message="已初始化 MAA 控制上下文", overview=self.get_overview())

    def refresh(self) -> DeviceOverview:
        return self.get_overview()

    def find_adb(self) -> DeviceActionResult:
        try:
            self._adb_raw = find_adb_devices()
            self._adb_page = 0
            return DeviceActionResult(ok=True, message=f"已搜索到 {len(self._adb_raw)} 个 ADB 设备", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"搜索 ADB 设备失败: {exc}", severity="error", overview=self.get_overview())

    def find_win32(self) -> DeviceActionResult:
        try:
            self._win32_raw = find_desktop_windows()
            self._win32_page = 0
            return DeviceActionResult(ok=True, message=f"已搜索到 {len(self._win32_raw)} 个 Win32 窗口", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"搜索 Win32 窗口失败: {exc}", severity="error", overview=self.get_overview())

    def change_adb_page(self, delta: int) -> DeviceOverview:
        self._adb_page = self._clamp_page(self._adb_page + delta, len(self._adb_raw))
        return self.get_overview()

    def change_win32_page(self, delta: int) -> DeviceOverview:
        self._win32_page = self._clamp_page(self._win32_page + delta, len(self._win32_raw))
        return self.get_overview()

    def connect_adb(self, request: ConnectAdbRequest) -> DeviceActionResult:
        address = request.address.strip()
        if not address:
            return DeviceActionResult(ok=False, message="请先输入 ADB 地址", severity="warning", overview=self.get_overview())

        global_cfg = self._get_global_config()
        adb_path = str(global_cfg.maa_adb_dir or "").strip() or "adb.exe"
        params = AdbConnectionParams(adb_path=adb_path, address=address)
        try:
            session = connect_adb(self._maa_facade.context, params)
            self._maa_facade.attach_session(session)
            return DeviceActionResult(ok=True, message=f"已连接 ADB 设备: {address}", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"连接 ADB 失败: {exc}", severity="error", overview=self.get_overview())

    def connect_device(self, action_id: str) -> DeviceActionResult:
        if action_id.startswith("adb:"):
            return self._connect_adb_item(action_id)
        if action_id.startswith("win32:"):
            return self._connect_win32_item(action_id)
        if action_id.startswith("emulator:"):
            return self._connect_emulator_item(action_id)
        if action_id.startswith("browser:"):
            return self._connect_browser_item(action_id)
        return DeviceActionResult(ok=False, message=f"未知设备动作: {action_id}", severity="error", overview=self.get_overview())

    def disconnect_device(self) -> DeviceActionResult:
        try:
            self._maa_facade.clear_session()
            return DeviceActionResult(ok=True, message="已断开当前设备连接", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"断开设备连接失败: {exc}", severity="error", overview=self.get_overview())

    def _capture_current_screenshot_result(self) -> DeviceActionResult:
        session = self._maa_facade.get_current_session()
        if session is None:
            return DeviceActionResult(
                ok=False,
                message="当前无已连接设备，无法截图",
                severity="warning",
                overview=self.get_overview()
            )

        image_data = screencap(self._maa_facade.context)

        if image_data is None:
            return DeviceActionResult(
                ok=False,
                message="截图获取失败：未返回有效的图像数据",
                severity="error",
                overview=self.get_overview()
            )

        try:
            img_arr = np.asarray(image_data)

            if len(img_arr.shape) == 3 and img_arr.shape[2] == 3:
                img_arr = img_arr[..., ::-1]

            img = Image.fromarray(img_arr)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return DeviceActionResult(
                ok=True,
                message="截图成功",
                severity="information",
                overview=self.get_overview(),
                image_base64=img_base64
            )

        except Exception as exc:
            return DeviceActionResult(
                ok=False,
                message=f"截图处理时发生异常: {exc}",
                severity="error",
                overview=self.get_overview()
            )

    def screencap_current(self) -> DeviceActionResult:
        return self._capture_current_screenshot_result()

    def screencap_current_and_save(self) -> DeviceActionResult:
        result = self._capture_current_screenshot_result()
        if not result.ok or not result.image_base64:
            return result

        try:
            temp_dir = Path("temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = temp_dir / f"screenshot_{timestamp}.png"
            screenshot_path.write_bytes(base64.b64decode(result.image_base64))
            result.message = f"截图成功，已保存到 {screenshot_path.as_posix()}"
            result.saved_path = screenshot_path.as_posix()
            return result
        except Exception as exc:
            return DeviceActionResult(
                ok=False,
                message=f"截图保存时发生异常: {exc}",
                severity="error",
                overview=self.get_overview(),
                image_base64=result.image_base64,
            )

    def _connect_adb_item(self, action_id: str) -> DeviceActionResult:
        idx = self._parse_index(action_id, len(self._adb_raw))
        if idx is None:
            return DeviceActionResult(ok=False, message="ADB 设备索引无效", severity="warning", overview=self.get_overview())

        device = self._adb_raw[idx]
        global_cfg = self._get_global_config()
        fallback_adb_path = str(global_cfg.maa_adb_dir or "").strip() or "adb.exe"
        params = AdbConnectionParams(
            adb_path=str(device.get("adb_path") or fallback_adb_path),
            address=str(device.get("address") or ""),
            screencap_methods=device.get("screencap_methods"),
            input_methods=device.get("input_methods"),
            config=device.get("config") or {},
        )
        if not params.address:
            return DeviceActionResult(ok=False, message="ADB 设备缺少地址信息", severity="error", overview=self.get_overview())

        try:
            session = connect_adb(self._maa_facade.context, params)
            self._maa_facade.attach_session(session)
            return DeviceActionResult(ok=True, message=f"已连接 ADB 设备: {params.address}", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"连接 ADB 设备失败: {exc}", severity="error", overview=self.get_overview())

    def _connect_win32_item(self, action_id: str) -> DeviceActionResult:
        idx = self._parse_index(action_id, len(self._win32_raw))
        if idx is None:
            return DeviceActionResult(ok=False, message="Win32 窗口索引无效", severity="warning", overview=self.get_overview())

        window = self._win32_raw[idx]
        hwnd = int(window.get("hwnd") or 0)
        if hwnd == 0:
            return DeviceActionResult(ok=False, message="当前窗口句柄无效，无法连接", severity="error", overview=self.get_overview())

        try:
            session = connect_win32(self._maa_facade.context, Win32ConnectionParams(hwnd=hwnd))
            self._maa_facade.attach_session(session)
            window_name = str(window.get("window_name") or hwnd)
            return DeviceActionResult(ok=True, message=f"已连接 Win32 窗口: {window_name}", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"连接 Win32 窗口失败: {exc}", severity="error", overview=self.get_overview())

    def _connect_emulator_item(self, action_id: str) -> DeviceActionResult:
        cfg = self._get_device_config()
        devices = cfg.get_mumu_devices()
        idx = self._parse_index(action_id, len(devices))
        if idx is None:
            return DeviceActionResult(ok=False, message="模拟器设备索引无效", severity="warning", overview=self.get_overview())

        device = devices[idx]
        global_cfg = self._get_global_config()
        adb_path = str(global_cfg.maa_adb_dir or "").strip() or "adb.exe"
        params = AdbConnectionParams(
            adb_path=adb_path,
            address=device.address,
            mumu=device.mumu,
        )
        if not params.address:
            return DeviceActionResult(ok=False, message="模拟器设备缺少地址信息", severity="error", overview=self.get_overview())

        try:
            session = connect_adb(self._maa_facade.context, params)
            self._maa_facade.attach_session(session)
            return DeviceActionResult(ok=True, message=f"已连接模拟器设备: {device.name}", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"连接模拟器设备失败: {exc}", severity="error", overview=self.get_overview())

    def _build_connection_state(self) -> DeviceConnectionState:
        session = self._maa_facade.get_current_session()
        raw_label = self._maa_facade.context.state.connection_label
        label = raw_label if isinstance(raw_label, str) and raw_label.strip() else None
        session_label = None
        if session is not None:
            raw_session_label = getattr(getattr(session, "info", None), "label", None)
            if isinstance(raw_session_label, str) and raw_session_label.strip():
                session_label = raw_session_label

        display_label = label or session_label
        connected = bool(session and display_label)
        return DeviceConnectionState(
            initialized=True,
            connected=connected,
            label=display_label,
            can_screencap=connected,
            screencap_label=f"截图测试: {display_label}" if connected else "当前无已连接的设备",
        )

    def _build_adb_page(self) -> DevicePage:
        items: list[DeviceListItem] = []
        total = len(self._adb_raw)
        page_index = self._clamp_page(self._adb_page, total)
        self._adb_page = page_index
        for absolute_idx, device in self._slice_page(self._adb_raw, page_index):
            tags: list[str] = []
            if device.get("emulator_type") == "mumu":
                tags.append("mumu")
            if device.get("kind") == "emulator":
                tags.append("emulator")
            items.append(
                DeviceListItem(
                    id=f"adb:{absolute_idx}",
                    kind=str(device.get("kind") or "adb"),
                    title=str(device.get("name") or "未命名设备"),
                    subtitle=str(device.get("address") or "未知地址"),
                    tags=tags,
                )
            )
        return self._build_page(total, page_index, items, empty_summary="未发现可用 ADB 设备", filled_summary=f"共发现 {total} 个 ADB 设备")

    def _build_win32_page(self) -> DevicePage:
        items: list[DeviceListItem] = []
        total = len(self._win32_raw)
        page_index = self._clamp_page(self._win32_page, total)
        self._win32_page = page_index
        for absolute_idx, window in self._slice_page(self._win32_raw, page_index):
            hwnd = int(window.get("hwnd") or 0)
            items.append(
                DeviceListItem(
                    id=f"win32:{absolute_idx}",
                    kind="win32",
                    title=str(window.get("window_name") or "未命名窗口"),
                    subtitle=f"[{hwnd}] {window.get('class_name') or '未知类名'}",
                    enabled=hwnd != 0,
                )
            )
        return self._build_page(total, page_index, items, empty_summary="未发现可控 Win32 窗口", filled_summary=f"共发现 {total} 个 Win32 窗口")

    def _build_emulator_page(self) -> DevicePage:
        cfg = self._get_device_config()
        items = [
            DeviceListItem(
                id=f"emulator:{index}",
                kind="emulator",
                title=device.name,
                subtitle=device.address,
                tags=["mumu"] if device.mumu and device.mumu.enable else [],
            )
            for index, device in enumerate(cfg.get_mumu_devices())
        ]
        total = len(items)
        return DevicePage(
            summary="暂无已配置模拟器设备" if total == 0 else f"已配置 {total} 个模拟器设备",
            page_index=0,
            page_count=1 if total else 0,
            total=total,
            has_prev=False,
            has_next=False,
            items=items,
        )

    def _build_browser_page(self) -> DevicePage:
        cfg = self._get_device_config()
        devices = cfg.get_browser_devices()
        items = [
            DeviceListItem(
                id=f"browser:{index}",
                kind="browser",
                title=device.name,
                subtitle=device.debug_url or device.executable_path,
                tags=[device.type, "cdp" if device.debug_url else "launch"],
            )
            for index, device in enumerate(devices)
        ]
        total = len(items)
        return DevicePage(
            summary="暂无已配置浏览器设备" if total == 0 else f"已配置 {total} 个浏览器设备",
            page_index=0,
            page_count=1 if total else 0,
            total=total,
            has_prev=False,
            has_next=False,
            items=items,
        )

    def _connect_browser_item(self, action_id: str) -> DeviceActionResult:
        cfg = self._get_device_config()
        devices = cfg.get_browser_devices()
        idx = self._parse_index(action_id, len(devices))
        if idx is None:
            return DeviceActionResult(ok=False, message="浏览器设备索引无效", severity="warning", overview=self.get_overview())

        device = devices[idx]
        params = device.to_connection_params()
        try:
            session = connect_browser(self._maa_facade.context, params)
            self._maa_facade.attach_session(session)
            return DeviceActionResult(ok=True, message=f"已连接浏览器设备: {device.name}", overview=self.get_overview())
        except Exception as exc:
            return DeviceActionResult(ok=False, message=f"连接浏览器设备失败: {exc}", severity="error", overview=self.get_overview())

    def _get_device_config(self) -> MaaDeviceConfig:
        try:
            return config.get(MaaDeviceConfig)
        except RuntimeError:
            load_config()
            return config.get(MaaDeviceConfig)

    def _get_global_config(self) -> GlobalConfig:
        try:
            return config.get(GlobalConfig)
        except RuntimeError:
            load_config()
            return config.get(GlobalConfig)

    def _build_page(self, total: int, page_index: int, items: list[DeviceListItem], *, empty_summary: str, filled_summary: str) -> DevicePage:
        if total == 0:
            return DevicePage(summary=empty_summary, page_index=0, page_count=0, total=0, has_prev=False, has_next=False, items=[])
        page_count = ceil(total / PAGE_SIZE)
        return DevicePage(
            summary=filled_summary,
            page_index=page_index,
            page_count=page_count,
            total=total,
            has_prev=page_index > 0,
            has_next=page_index + 1 < page_count,
            items=items,
        )

    def _slice_page(self, items: list[dict], page_index: int) -> list[tuple[int, dict]]:
        start = page_index * PAGE_SIZE
        end = start + PAGE_SIZE
        return list(enumerate(items[start:end], start=start))

    def _clamp_page(self, page_index: int, total: int) -> int:
        if total <= 0:
            return 0
        page_count = ceil(total / PAGE_SIZE)
        return max(0, min(page_index, page_count - 1))

    def _parse_index(self, action_id: str, total: int) -> int | None:
        try:
            idx = int(action_id.split(":", 1)[1])
        except Exception:
            return None
        if idx < 0 or idx >= total:
            return None
        return idx


_global_device_facade = DeviceFacade()


def get_device_facade() -> DeviceFacade:
    return _global_device_facade
