from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceListItem(BaseModel):
    """通用设备列表项"""

    id: str
    kind: str
    title: str
    subtitle: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class DevicePage(BaseModel):
    """分页后的设备列表"""

    summary: str
    page_index: int = 0
    page_count: int = 0
    total: int = 0
    has_prev: bool = False
    has_next: bool = False
    items: list[DeviceListItem] = Field(default_factory=list)


class DeviceConnectionState(BaseModel):
    """当前连接摘要"""

    initialized: bool = False
    connected: bool = False
    label: str | None = None
    can_screencap: bool = False
    screencap_label: str = "当前无已连接的设备"


class DeviceOverview(BaseModel):
    """设备模块面向前端暴露的通用状态聚合"""

    adb: DevicePage = Field(default_factory=lambda: DevicePage(summary="尚未搜索 ADB 设备"))
    win32: DevicePage = Field(default_factory=lambda: DevicePage(summary="尚未搜索 Win32 窗口"))
    emulator: DevicePage = Field(default_factory=lambda: DevicePage(summary="暂无已配置模拟器设备"))
    browser: DevicePage = Field(default_factory=lambda: DevicePage(summary="暂无已配置浏览器设备"))
    connection: DeviceConnectionState = Field(default_factory=DeviceConnectionState)


class ConnectAdbRequest(BaseModel):
    """手动连接 ADB 请求"""

    address: str


class DeviceActionResult(BaseModel):
    """设备域操作返回结果"""

    ok: bool
    message: str
    severity: str = "information"
    overview: DeviceOverview | None = None
    image_base64: str | None = None
    saved_path: str | None = None
