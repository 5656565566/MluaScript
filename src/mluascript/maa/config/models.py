from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mluascript.maa.connections.models import BrowserConnectionParams, MuMuConfig
from mluascript.shared.config.registry import config


class AdbDeviceConfig(BaseModel):
    """ADB 设备配置（仅 WiFi 设备）"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="设备名称/标识")
    address: str = Field(description="ADB 地址，如: 192.168.1.100:5555")
    description: str | None = Field(default=None, description="设备描述")
    mumu: MuMuConfig | None = Field(default=None, description="MuMu 模拟器配置，仅当设备为 MuMu 时使用")
    extra: dict[str, object] = Field(default_factory=dict, description="其他扩展配置")

    @model_validator(mode="after")
    def validate_device(self) -> "AdbDeviceConfig":
        if not self.name:
            self.name = f"设备_{self.address}"
        return self


class BrowserDeviceConfig(BaseModel):
    """浏览器设备配置"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="浏览器设备名称")
    type: str = Field(description="浏览器类型，如 chrome/edge/brave/firefox")
    executable_path: str = Field(default="", description="浏览器可执行文件路径")
    debug_url: str = Field(default="", description="浏览器调试地址")
    description: str | None = Field(default=None, description="浏览器描述")
    extra_args: list[str] = Field(default_factory=list, description="额外启动参数")
    profile_dir: str = Field(default="", description="浏览器用户目录")

    @model_validator(mode="after")
    def validate_browser_device(self) -> "BrowserDeviceConfig":
        self.type = str(self.type or "").strip().lower()
        self.executable_path = str(self.executable_path or "").strip()
        self.debug_url = str(self.debug_url or "").strip()
        if not self.name:
            self.name = f"浏览器_{self.type or 'unknown'}"
        return self

    def is_visible(self) -> bool:
        return bool(self.type and (self.executable_path or self.debug_url))

    def to_connection_params(self) -> BrowserConnectionParams:
        return BrowserConnectionParams(
            url=self.debug_url or "http://localhost:9222",
            browser_type=self.type,
            executable_path=self.executable_path,
            launch_args=list(self.extra_args),
            profile_dir=self.profile_dir,
            name=self.name,
        )


@config.registry()
class MaaDeviceConfig(BaseModel):
    """Maa 设备连接相关配置"""

    model_config = ConfigDict(extra="allow")

    adb_devices: list[AdbDeviceConfig] = Field(
        default_factory=lambda: [
            AdbDeviceConfig(
                name="示例WiFi设备",
                address="192.168.1.100:5555",
                description="通过 WiFi 连接的 Android 设备",
            ),
            AdbDeviceConfig(
                name="MuMu模拟器",
                address="127.0.0.1:7555",
                mumu=MuMuConfig(
                    enable=True,
                    path="xxx",
                    lib="shell",
                    index=0,
                    app_package="com.example.app",
                    app_cloned_index=0,
                ),
                description="MuMu 模拟器配置",
            ),
        ],
        description="WiFi ADB 设备列表",
    )
    browser_devices: list[BrowserDeviceConfig] = Field(
        default_factory=lambda: [
            BrowserDeviceConfig(
                name="Chrome 调试实例",
                type="chrome",
                debug_url="http://127.0.0.1:9222",
                description="通过 CDP 连接的 Chrome 浏览器",
            )
        ],
        description="浏览器设备列表",
    )

    def get_device_by_name(self, name: str) -> AdbDeviceConfig | None:
        for device in self.adb_devices:
            if device.name == name:
                return device
        return None

    def get_device_by_address(self, address: str) -> AdbDeviceConfig | None:
        for device in self.adb_devices:
            if device.address == address:
                return device
        return None

    def get_mumu_devices(self) -> list[AdbDeviceConfig]:
        return [device for device in self.adb_devices if device.mumu and device.mumu.enable]

    def get_wifi_devices(self) -> list[AdbDeviceConfig]:
        return self.adb_devices

    def get_browser_devices(self) -> list[BrowserDeviceConfig]:
        return [device for device in self.browser_devices if device.is_visible()]
