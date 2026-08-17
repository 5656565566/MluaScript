from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from mluascript.maa.connections.adb import connect_adb
from mluascript.maa.connections.browser import connect_browser
from mluascript.maa.connections.desktop import connect_desktop_window, current_desktop_backend
from mluascript.maa.connections.discovery import find_adb_devices, find_desktop_windows
from mluascript.maa.connections.models import AdbConnectionParams, BrowserConnectionParams, DesktopWindowConnectionParams
from mluascript.maa.extensions.browser.controller import BrowserController
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths


def build_context() -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
    )


def test_connect_adb_marks_context_connected(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mocker.patch("mluascript.maa.connections.adb.AdbController", return_value=mock_controller)

    session = connect_adb(context, AdbConnectionParams(adb_path="adb.exe", address="127.0.0.1:5555"))

    assert session.info.kind == "adb"
    assert session.info.label == "ADB:127.0.0.1:5555"
    assert session.info.meta == {"address": "127.0.0.1:5555", "adb_path": "adb.exe"}
    assert context.state.connected is True
    assert context.state.connection_label == "ADB:127.0.0.1:5555"



def test_connect_adb_uses_emulator_extras_for_mumu(mocker) -> None:
    from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum
    from mluascript.maa.connections.models import MuMuConfig

    context = build_context()
    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mock_adb_controller = mocker.patch("mluascript.maa.connections.adb.AdbController", return_value=mock_controller)

    connect_adb(
        context,
        AdbConnectionParams(
            adb_path="adb.exe",
            address="127.0.0.1:7555",
            mumu=MuMuConfig(
                enable=True,
                path="xxx",
                lib="shell",
                index=0,
                app_package="com.example.app",
                app_cloned_index=0,
            ),
        ),
    )

    _, kwargs = mock_adb_controller.call_args
    assert kwargs["screencap_methods"] == int(MaaAdbScreencapMethodEnum.EmulatorExtras)
    assert kwargs["input_methods"] == int(MaaAdbInputMethodEnum.EmulatorExtras)
    assert kwargs["config"]["extras"]["mumu"]["app_package"] == "com.example.app"


def test_connect_browser_marks_context_connected(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mocker.patch("mluascript.maa.connections.browser.BrowserController", return_value=mock_controller)

    session = connect_browser(context, BrowserConnectionParams(url="http://localhost:9222"))

    assert session.info.kind == "browser"
    assert session.info.label == "BROWSER:http://localhost:9222"
    assert session.info.meta == {
        "url": "http://localhost:9222",
        "browser_type": "chrome",
        "executable_path": "",
        "name": "",
    }
    assert context.state.connected is True
    assert context.state.connection_label == "BROWSER:http://localhost:9222"



def test_connect_browser_passes_launch_configuration(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mock_browser_controller = mocker.patch("mluascript.maa.connections.browser.BrowserController", return_value=mock_controller)

    connect_browser(
        context,
        BrowserConnectionParams(
            url="http://127.0.0.1:9333",
            browser_type="edge",
            executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            launch_args=["--new-window"],
            profile_dir=".mluascript_web/browser/edge-1",
            name="Edge-1",
        ),
    )

    args, kwargs = mock_browser_controller.call_args
    assert args[0] == "http://127.0.0.1:9333"
    assert kwargs["browser_type"] == "edge"
    assert kwargs["executable_path"].endswith("msedge.exe")
    assert kwargs["launch_args"] == ["--new-window"]
    assert kwargs["profile_dir"] == ".mluascript_web/browser/edge-1"
    assert kwargs["name"] == "Edge-1"


def test_browser_controller_sends_virtual_keys_to_playwright(mocker) -> None:
    controller = BrowserController.__new__(BrowserController)
    controller._connected = True
    controller.browser = None
    controller.page = mocker.MagicMock()
    controller.page.is_closed.return_value = False

    assert controller.click_key(13) is True
    assert controller.key_down(65) is True
    assert controller.key_up(65) is True
    assert controller.click_key(999) is False

    controller.page.keyboard.press.assert_called_once_with("Enter")
    controller.page.keyboard.down.assert_called_once_with("A")
    controller.page.keyboard.up.assert_called_once_with("A")


def test_browser_controller_screencap_returns_contiguous_bgr_data(mocker) -> None:
    screenshot = io.BytesIO()
    Image.new("RGB", (1, 1), (12, 34, 56)).save(screenshot, format="PNG")
    controller = BrowserController.__new__(BrowserController)
    controller._connected = True
    controller.browser = None
    controller.page = mocker.MagicMock()
    controller.page.is_closed.return_value = False
    controller.page.screenshot.return_value = screenshot.getvalue()

    image = controller.screencap()

    assert image.flags.c_contiguous
    np.testing.assert_array_equal(image, np.array([[[56, 34, 12]]], dtype=np.uint8))


def test_browser_controller_uses_a_dedicated_profile_for_cdp_launch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("mluascript.shared.config.manager.get_runtime_dir", lambda: tmp_path)
    controller = BrowserController.__new__(BrowserController)
    controller.url = "http://127.0.0.1:9222"
    controller.browser_type = "chrome"
    controller.name = "Chrome 调试实例"
    controller.profile_dir = "C:/Users/example/AppData/Local/Google/Chrome/User Data"

    args = controller._default_launch_args()

    profile_arg = next(arg for arg in args if arg.startswith("--user-data-dir="))
    profile_path = Path(profile_arg.split("=", 1)[1])
    assert "--remote-debugging-port=9222" in args
    assert "--remote-debugging-address=127.0.0.1" in args
    assert profile_path == tmp_path / ".mluascript" / "browser" / "chrome-9222"
    assert profile_path.is_dir()


def test_connect_desktop_window_uses_windows_backend(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mocker.patch("mluascript.maa.connections.desktop.Win32Controller", return_value=mock_controller)

    session = connect_desktop_window(context, DesktopWindowConnectionParams(handle=1001, platform="windows"))

    assert session.info.kind == "desktop"
    assert session.info.label == "DESKTOP:windows:1001"
    assert session.info.meta == {"platform": "windows", "handle": 1001}
    assert context.state.connected is True
    assert context.state.connection_label == "DESKTOP:windows:1001"


def test_connect_desktop_window_uses_macos_backend(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mocker.patch("mluascript.maa.connections.desktop.MacOSController", return_value=mock_controller)

    session = connect_desktop_window(context, DesktopWindowConnectionParams(handle=2002, platform="macos"))

    assert session.info.kind == "desktop"
    assert session.info.label == "DESKTOP:macos:2002"
    assert session.info.meta == {"platform": "macos", "handle": 2002}


def test_current_desktop_backend_detects_linux_x11(monkeypatch, mocker) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    mocker.patch("mluascript.maa.connections.desktop.platform.system", return_value="Linux")

    assert current_desktop_backend() == "x11"


def test_connect_desktop_window_rejects_linux_x11_with_clear_message() -> None:
    context = build_context()

    with pytest.raises(RuntimeError, match="X11"):
        connect_desktop_window(context, DesktopWindowConnectionParams(handle=1, platform="x11"))


def test_discovery_returns_mocked_results(mocker) -> None:
    mock_toolkit = mocker.patch("mluascript.maa.connections.discovery.Toolkit")
    mock_toolkit.find_adb_devices.return_value = []
    mock_toolkit.find_desktop_windows.return_value = []

    assert find_adb_devices() == []
    assert find_desktop_windows() == []



def test_discovery_marks_mumu_device_as_emulator(mocker) -> None:
    mock_toolkit = mocker.patch("mluascript.maa.connections.discovery.Toolkit")
    mock_device = MagicMock()
    mock_device.name = "MuMu模拟器"
    mock_device.adb_path = Path("adb.exe")
    mock_device.address = "127.0.0.1:7555"
    mock_device.screencap_methods = 1
    mock_device.input_methods = 2
    mock_device.config = {
        "extras": {
            "mumu": {
                "enable": True,
                "path": "xxx",
                "lib": "shell",
                "index": 0,
                "app_package": "com.example.app",
                "app_cloned_index": 0,
            }
        }
    }
    mock_toolkit.find_adb_devices.return_value = [mock_device]

    assert find_adb_devices() == [
        {
            "name": "MuMu模拟器",
            "adb_path": "adb.exe",
            "address": "127.0.0.1:7555",
            "screencap_methods": 1,
            "input_methods": 2,
            "config": {
                "extras": {
                    "mumu": {
                        "enable": True,
                        "path": "xxx",
                        "lib": "shell",
                        "index": 0,
                        "app_package": "com.example.app",
                        "app_cloned_index": 0,
                    }
                }
            },
            "mumu": {
                "enable": True,
                "path": "xxx",
                "lib": "shell",
                "index": 0,
                "app_package": "com.example.app",
                "app_cloned_index": 0,
            },
            "kind": "emulator",
            "emulator_type": "mumu",
        }
    ]


def test_discovery_maps_desktop_windows(mocker) -> None:
    mock_toolkit = mocker.patch("mluascript.maa.connections.discovery.Toolkit")
    mock_window = MagicMock()
    mock_window.hwnd = 10086
    mock_window.class_name = "Notepad"
    mock_window.window_name = "无标题 - 记事本"
    mock_toolkit.find_desktop_windows.return_value = [mock_window]

    assert find_desktop_windows() == [
        {
            "hwnd": 10086,
            "handle": 10086,
            "class_name": "Notepad",
            "window_name": "无标题 - 记事本",
            "platform": "windows",
            "kind": "desktop",
        }
    ]
