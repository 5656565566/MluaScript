from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConnectionInfo(BaseModel):
    """已建立连接的信息摘要"""
    model_config = ConfigDict(extra="allow")

    kind: str
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class MuMuConfig(BaseModel):
    """MuMu 模拟器配置"""
    model_config = ConfigDict(extra="allow")

    enable: bool = Field(default=False, description="是否启用 MuMu 模拟器")
    path: str = Field(default="", description="MuMu 模拟器安装路径")
    lib: str = Field(default="", description="MuMu 模拟器库路径")
    index: int = Field(default=0, description="MuMu 模拟器索引")
    app_package: str = Field(default="", description="应用包名")
    app_cloned_index: int = Field(default=0, description="应用克隆索引")


class AdbConnectionParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    adb_path: str = Field(description="ADB 路径")
    address: str = Field(description="ADB 地址")
    screencap_methods: int | None = Field(default=None, description="截图方法")
    input_methods: int | None = Field(default=None, description="输入方法")
    config: dict[str, Any] = Field(default_factory=dict, description="额外配置")
    mumu: Optional[MuMuConfig] = Field(default=None, description="MuMu 模拟器配置")


class Win32ConnectionParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    hwnd: int = Field(description="窗口句柄")
    screencap_method: int | None = Field(default=None, description="截图方法")
    mouse_method: int | None = Field(default=None, description="鼠标方法")
    keyboard_method: int | None = Field(default=None, description="键盘方法")


class BrowserConnectionParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(default="http://localhost:9222", description="浏览器调试地址")
    browser_type: str = Field(default="chrome", description="浏览器类型")
    executable_path: str = Field(default="", description="浏览器可执行文件路径")
    launch_args: list[str] = Field(default_factory=list, description="浏览器启动参数")
    profile_dir: str = Field(default="", description="浏览器用户目录")
    name: str = Field(default="", description="浏览器名称")
