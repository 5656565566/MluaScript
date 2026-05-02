from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mluascript.maa.connections.adb import connect_adb
from mluascript.maa.connections.browser import connect_browser
from mluascript.maa.connections.discovery import find_adb_devices, find_desktop_windows
from mluascript.maa.connections.models import AdbConnectionParams, BrowserConnectionParams, Win32ConnectionParams
from mluascript.maa.connections.win32 import connect_win32
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


def test_connect_win32_marks_context_connected(mocker) -> None:
    context = build_context()

    mock_controller = MagicMock()
    mock_job = MagicMock()
    mock_job.succeeded = True
    mock_controller.post_connection.return_value = mock_job
    mock_controller.post_screencap.return_value = mock_job
    mocker.patch("mluascript.maa.connections.win32.Win32Controller", return_value=mock_controller)

    session = connect_win32(context, Win32ConnectionParams(hwnd=1001))

    assert session.info.kind == "win32"
    assert session.info.label == "WIN32:1001"
    assert session.info.meta == {"hwnd": 1001}
    assert context.state.connected is True
    assert context.state.connection_label == "WIN32:1001"


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
            "class_name": "Notepad",
            "window_name": "无标题 - 记事本",
        }
    ]
