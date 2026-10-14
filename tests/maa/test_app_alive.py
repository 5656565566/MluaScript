from __future__ import annotations

import csv
import io
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import psutil
from lupa.lua54 import LuaRuntime

from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.lua_exports import build_maa_exports
from mluascript.maa.types import MaaContextState, MaaPaths


def build_exports(label: str | None):
    context = MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(connection_label=label),
    )
    return build_maa_exports(LuaRuntime(unpack_returned_tuples=True), context)


def csv_process(name: str) -> str:
    output = io.StringIO()
    csv.writer(output).writerow([name, "1234", "Console", "1", "10,000 K"])
    return output.getvalue()


@pytest.mark.parametrize("intent, output, expected", [
    ("notepad.exe", csv_process("notepad.exe"), True),
    ("NOTEPAD.EXE", csv_process("notepad.exe"), True),
    ("中文 application.exe", csv_process("中文 application.exe"), True),
    ("notepad.exe", csv_process("notepad.exe.backup"), False),
    ("notepad.exe", "INFO: No tasks match notepad.exe.\n", False),
    ("notepad.exe", "notepad.exe,invalid PID\n", False),
    ("notepad.exe", "notepad.exe\n", False),
    ("notepad.exe", "", False),
])
def test_windows_app_alive_matches_only_complete_process_names(mocker, intent, output, expected) -> None:
    exports = build_exports("DESKTOP:windows:1001")
    controller_shell = mocker.patch("mluascript.maa.lua_exports.shell", return_value=None)
    legacy_query = mocker.patch("mluascript.maa.lua_exports.subprocess.check_output", return_value=output)
    query = mocker.patch("mluascript.maa.lua_exports.subprocess.run", return_value=SimpleNamespace(
        returncode=0, stdout=output, stderr="",
    ))

    assert exports.is_app_alive(intent) is expected
    query.assert_called_once_with(
        ["tasklist.exe", "/FI", f"IMAGENAME eq {intent}", "/FO", "CSV", "/NH"],
        shell=False, capture_output=True, text=True, encoding="oem", timeout=20,
    )
    controller_shell.assert_not_called()
    legacy_query.assert_not_called()


@pytest.mark.parametrize("intent", [
    'notepad.exe" & echo MLUASCRIPT_PROBE & rem "',
    "notepad.exe; echo MLUASCRIPT_PROBE",
    "notepad.exe | echo MLUASCRIPT_PROBE",
    "$(echo MLUASCRIPT_PROBE)",
    "`echo MLUASCRIPT_PROBE`",
])
def test_windows_app_alive_keeps_untrusted_input_in_one_filter_argument(mocker, intent) -> None:
    exports = build_exports("DESKTOP:windows:1001")
    mocker.patch("mluascript.maa.lua_exports.shell", return_value=None)
    legacy_query = mocker.patch("mluascript.maa.lua_exports.subprocess.check_output")
    query = mocker.patch("mluascript.maa.lua_exports.subprocess.run", return_value=SimpleNamespace(
        returncode=0, stdout="INFO: No tasks are running.\n", stderr="",
    ))

    assert exports.is_app_alive(intent) is False
    assert query.call_count == 1
    assert query.call_args.args[0] == [
        "tasklist.exe", "/FI", f"IMAGENAME eq {intent}", "/FO", "CSV", "/NH",
    ]
    assert query.call_args.kwargs["shell"] is False
    legacy_query.assert_not_called()


@pytest.mark.parametrize("result", [
    SimpleNamespace(returncode=1, stdout="", stderr="Access denied"),
    subprocess.TimeoutExpired("tasklist.exe", 20),
    FileNotFoundError("tasklist.exe"),
])
def test_windows_app_alive_reports_query_failures(mocker, result) -> None:
    exports = build_exports("DESKTOP:windows:1001")
    mocker.patch("mluascript.maa.lua_exports.shell", return_value=None)
    mocker.patch("mluascript.maa.lua_exports.subprocess.check_output")
    query = mocker.patch("mluascript.maa.lua_exports.subprocess.run")
    if isinstance(result, Exception):
        query.side_effect = result
    else:
        query.return_value = result
    warning = mocker.patch("mluascript.maa.lua_exports.logger.warning")

    assert exports.is_app_alive("notepad.exe") is False
    query.assert_called_once()
    warning.assert_called_once()


@pytest.mark.parametrize("output, expected", [
    ("1234\n", True),
    ("1234 5678\n", True),
    (None, False),
    ("", False),
    (" \n", False),
    ("pidof: not found", False),
    ("0", False),
    ("1234 error", False),
    ("１２３４", False),
])
def test_adb_app_alive_requires_valid_process_ids(mocker, output, expected) -> None:
    exports = build_exports("ADB:test")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell", return_value=output)

    assert exports.is_app_alive("com.example.app:worker") is expected
    device_shell.assert_called_once_with(exports.context, "pidof com.example.app:worker")


@pytest.mark.parametrize("intent", [
    "com.example.app; echo MLUASCRIPT_PROBE",
    "com.example.app && echo MLUASCRIPT_PROBE",
    "$(echo MLUASCRIPT_PROBE)",
    "`echo MLUASCRIPT_PROBE`",
    "process with 'single' and \"double\" quotes",
    "中文 process",
])
def test_adb_app_alive_quotes_process_name_as_one_shell_argument(mocker, intent) -> None:
    exports = build_exports("ADB:test")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell", return_value="")

    assert exports.is_app_alive(intent) is False
    command = device_shell.call_args.args[1]
    assert shlex.split(command) == ["pidof", intent]


@pytest.mark.parametrize("label", ["ADB:test", "DESKTOP:windows:1001"])
@pytest.mark.parametrize("intent", ["", " \t\n", "notepad.exe\0ignored"])
def test_app_alive_rejects_empty_and_nul_input_without_querying(mocker, label, intent) -> None:
    exports = build_exports(label)
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell", return_value="")
    legacy_query = mocker.patch("mluascript.maa.lua_exports.subprocess.check_output")
    query = mocker.patch("mluascript.maa.lua_exports.subprocess.run")

    assert exports.is_app_alive(intent) is False
    device_shell.assert_not_called()
    legacy_query.assert_not_called()
    query.assert_not_called()


def test_app_alive_returns_false_for_unconnected_context(mocker) -> None:
    exports = build_exports(None)
    query = mocker.patch("mluascript.maa.lua_exports.subprocess.run")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell")

    assert exports.is_app_alive("notepad.exe") is False
    query.assert_not_called()
    device_shell.assert_not_called()


@pytest.mark.parametrize("label", ["DESKTOP:macos:1001", "DESKTOP:wlroots:/run/user/1000/wayland-0"])
@pytest.mark.parametrize("intent, processes, expected", [
    ("firefox", [{"name": "firefox", "exe": "/usr/bin/firefox"}], True),
    ("Firefox", [{"name": "firefox", "exe": "/usr/bin/firefox"}], False),
    ("firefox", [{"name": "firefox-helper", "exe": "/usr/bin/firefox-helper"}], False),
    ("very-long-application-name", [{"name": "very-long-appli", "exe": "/opt/very-long-application-name"}], True),
    ("Google Chrome", [{"name": "Google Chrome", "exe": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}], True),
    ("中文 application", [{"name": "中文 application", "exe": "/opt/中文 application"}], True),
    ("app\\name", [{"name": None, "exe": "/opt/app\\name"}], True),
    ("unavailable", [{"name": None, "exe": None}], False),
    ("firefox", [{"name": None, "exe": None}, {"name": "firefox", "exe": None}], True),
    ("firefox", [], False),
    ("firefox; echo MLUASCRIPT_PROBE", [{"name": "firefox", "exe": "/usr/bin/firefox"}], False),
])
def test_unix_app_alive_matches_process_or_executable_names(mocker, label, intent, processes, expected) -> None:
    exports = build_exports(label)
    mocker.patch("mluascript.maa.lua_exports.psutil.process_iter", return_value=iter(
        SimpleNamespace(info=process) for process in processes
    ))
    local_query = mocker.patch("mluascript.maa.lua_exports.subprocess.run")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell")

    assert exports.is_app_alive(intent) is expected
    local_query.assert_not_called()
    device_shell.assert_not_called()


@pytest.mark.parametrize("label", ["DESKTOP:macos:1001", "DESKTOP:wlroots:/run/user/1000/wayland-0"])
@pytest.mark.parametrize("error", [OSError("Process query failed"), psutil.AccessDenied(pid=1234)])
def test_unix_app_alive_reports_enumeration_failures(mocker, label, error) -> None:
    exports = build_exports(label)
    mocker.patch("mluascript.maa.lua_exports.psutil.process_iter", side_effect=error)
    warning = mocker.patch("mluascript.maa.lua_exports.logger.warning")

    assert exports.is_app_alive("firefox") is False
    warning.assert_called_once()


@pytest.mark.parametrize("label", ["DESKTOP:macos:1001", "DESKTOP:wlroots:wayland-0"])
@pytest.mark.parametrize("status, expected", [
    (psutil.STATUS_SLEEPING, True),
    (psutil.STATUS_STOPPED, True),
    (psutil.STATUS_ZOMBIE, False),
    (psutil.STATUS_DEAD, False),
])
def test_unix_app_alive_excludes_exited_process_states(mocker, label, status, expected) -> None:
    exports = build_exports(label)
    mocker.patch("mluascript.maa.lua_exports.psutil.process_iter", return_value=iter([
        SimpleNamespace(info={"name": "firefox", "exe": "/usr/bin/firefox", "status": status}),
    ]))

    assert exports.is_app_alive("firefox") is expected


def test_browser_app_alive_remains_unsupported(mocker) -> None:
    exports = build_exports("BROWSER:http://remote-host:9222")
    processes = mocker.patch("mluascript.maa.lua_exports.psutil.process_iter")
    local_query = mocker.patch("mluascript.maa.lua_exports.subprocess.run")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell")

    assert exports.is_app_alive("chrome") is False
    processes.assert_not_called()
    local_query.assert_not_called()
    device_shell.assert_not_called()


@pytest.mark.integration
@pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Requires Linux or macOS processes")
def test_unix_app_alive_checks_a_real_child_and_detects_its_exit(tmp_path) -> None:
    label = "DESKTOP:macos:1001" if sys.platform == "darwin" else "DESKTOP:wlroots:wayland-0"
    exports = build_exports(label)
    name = f"maa app alive {os.getpid()} 中文"
    executable = tmp_path / name
    shutil.copy2("/bin/sleep", executable)
    process = subprocess.Popen([str(executable), "30"])
    try:
        assert exports.is_app_alive(name) is True
        assert exports.is_app_alive("mluascript-no-such-process-93a15b") is False
        assert exports.is_app_alive(f"{name}; echo MLUASCRIPT_PROBE") is False
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert exports.is_app_alive(name) is False


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="Requires Linux waitid with WNOWAIT")
def test_linux_app_alive_returns_false_before_exited_child_is_reaped(tmp_path) -> None:
    exports = build_exports("DESKTOP:wlroots:wayland-0")
    name = f"maaZ{os.getpid()}"
    executable = tmp_path / name
    shutil.copy2("/bin/sleep", executable)
    process = subprocess.Popen([str(executable), "30"])
    try:
        assert exports.is_app_alive(name) is True
        process.terminate()
        os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
        assert psutil.Process(process.pid).status() == psutil.STATUS_ZOMBIE
        assert exports.is_app_alive(name) is False
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows tasklist")
def test_windows_app_alive_checks_real_processes_and_blocks_command_execution(tmp_path, mocker) -> None:
    exports = build_exports("DESKTOP:windows:1001")
    device_shell = mocker.patch("mluascript.maa.lua_exports.shell", return_value=None)
    marker = tmp_path / "injected-command.txt"

    assert exports.is_app_alive(Path(sys.executable).name.upper()) is True
    assert exports.is_app_alive("mluascript-no-such-process-93a15b.exe") is False
    payload = f'notepad.exe" & echo MLUASCRIPT_PROBE > "{marker}" & rem "'
    assert exports.is_app_alive(payload) is False
    assert not marker.exists()
    device_shell.assert_not_called()
