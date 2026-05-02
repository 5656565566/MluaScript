from __future__ import annotations

import time
from pathlib import Path

from mluascript.control.execution.manager import ExecutionManager
from mluascript.control.facade import ControlFacade
from mluascript.control.state.manager import StateManager
from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.shared.config.manager import load_config


def _build_real_facade(root_dir: Path) -> ControlFacade:
    load_config(str(root_dir / "config.yaml"))
    facade = ControlFacade()
    facade.state_mgr = StateManager()
    facade.workspace_mgr = WorkspaceManager(root_dir)
    exec_mgr = ExecutionManager()
    exec_mgr.script_use_case.state_manager = facade.state_mgr
    exec_mgr.pipeline_use_case.state_manager = facade.state_mgr
    exec_mgr.script_use_case.workspace_manager = facade.workspace_mgr
    exec_mgr.pipeline_use_case.workspace_manager = facade.workspace_mgr
    facade.exec_mgr = exec_mgr
    return facade


def _wait_for_terminal_status(facade: ControlFacade, task_id: str, timeout: float = 3.0) -> str:
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        task = facade.get_task_info(task_id)
        if task is None:
            time.sleep(0.02)
            continue
        last_status = task.status
        if task.status in {"success", "failed", "stopped"}:
            return task.status
        time.sleep(0.02)
    return last_status


def test_control_facade_run_script_executes_real_lua(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_path = project_dir / "test.lua"
    code = "return 40 + 2"
    script_path.write_text(code, encoding="utf-8")

    facade = _build_real_facade(tmp_path)

    task_id = facade.run_script("demo/test.lua", code, "ADB:real")
    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "success"
    assert task is not None
    assert task.result == 42


def test_control_facade_stop_script_stops_real_lua_runtime(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_path = project_dir / "loop.lua"
    code = "while true do sleep(0.05) end"
    script_path.write_text(code, encoding="utf-8")

    facade = _build_real_facade(tmp_path)

    task_id = facade.run_script("demo/loop.lua", code, "ADB:stop")
    time.sleep(0.15)
    facade.stop_script(task_id)

    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "stopped"
    assert task is not None
    assert task.status == "stopped"


def test_control_facade_run_script_uses_real_workspace_locator_for_relative_resource(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_path = project_dir / "test.lua"
    asset_path = project_dir / "xxx.txt"
    asset_path.write_text("hello-workspace", encoding="utf-8")
    code = "local f = io.open(path .. '/xxx.txt', 'r'); local c = f:read('*a'); f:close(); return c"
    script_path.write_text(code, encoding="utf-8")

    facade = _build_real_facade(tmp_path)

    task_id = facade.run_script("demo/test.lua", code, "ADB:asset")
    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "success"
    assert task is not None
    assert task.result == "hello-workspace"
