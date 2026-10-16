from __future__ import annotations

import time
import gc
import weakref
from threading import Event, enumerate as enumerate_threads
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mluascript.control.execution.manager import ExecutionManager
from mluascript.control.facade import ControlFacade
from mluascript.control.state.manager import StateManager
from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.shared.config.manager import load_config
import pytest


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


@pytest.mark.parametrize("ending, expected", [("return 42", "success"), ("error('main failed')", "failed")])
def test_script_completion_cancels_and_joins_owned_children(tmp_path, ending, expected):
    facade = _build_real_facade(tmp_path)
    code = f'function child() while true do end end; thread.spawn("child", "owned-lifecycle-child"); {ending}'
    task_id = facade.run_script('parent.lua', code, 'lifecycle-device')
    assert _wait_for_terminal_status(facade, task_id) == expected
    assert not any(thread.name == 'owned-lifecycle-child' for thread in enumerate_threads())
    context = facade.state_mgr.get_run_context(task_id)
    if context is not None:
        assert context.host_task.join(1)
    assert facade.state_mgr.get_run_context(task_id) is None


def test_completed_runs_release_lua_engines_even_with_global_task_handles(tmp_path):
    facade = _build_real_facade(tmp_path)
    integration = facade.exec_mgr.integration_facade
    create = integration.create_script_run
    engines = []

    def capture(*args, **kwargs):
        context = create(*args, **kwargs)
        engines.append(weakref.ref(context.runtime))
        return context

    integration.create_script_run = capture
    code = 'function worker() return 42 end; handle = thread.spawn("worker"); assert(handle:join(2)); return handle:result()'
    for _ in range(3):
        task_id = facade.run_script('handles.lua', code, 'engine-release-device')
        assert _wait_for_terminal_status(facade, task_id) == 'success'
    gc.collect()
    assert all(reference() is None for reference in engines)


@pytest.mark.parametrize("stop_fails", [False, True])
def test_stop_retains_native_child_and_device_admission_until_it_exits(tmp_path, monkeypatch, stop_fails):
    facade = _build_real_facade(tmp_path)
    entered, release = Event(), Event()
    use_case = facade.exec_mgr.script_use_case
    execute = use_case._execute_script

    def execute_with_probe(runtime, code):
        def block():
            entered.set()
            runtime.global_shared_store.set_key('entered', True)
            assert release.wait(5)
        runtime.register_namespace('probe', lambda lua: {'block': block})
        return execute(runtime, code)

    use_case._execute_script = execute_with_probe
    code = '''
        function child() probe.block() end
        thread.spawn("child", "owned-native-child")
        while not shared.get_key("entered") do sleep(0.005) end
        return 42
    '''
    task_id = facade.run_script('parent.lua', code, 'native-child-device')
    try:
        assert entered.wait(2)
        start = time.monotonic()
        if stop_fails:
            context = facade.state_mgr.get_run_context(task_id)
            def fail_stop():
                raise RuntimeError('native stop failed')
            monkeypatch.setattr(context.maa.tasker, 'post_stop', fail_stop)
            with pytest.raises(RuntimeError, match='native stop failed'):
                facade.stop_script(task_id)
        else:
            facade.stop_script(task_id)
        assert time.monotonic() - start < 0.8
        assert facade.get_task_info(task_id).status == 'pending'
        assert facade.state_mgr.get_run_context(task_id) is not None
        with pytest.raises(RuntimeError, match='已有任务'):
            facade.run_script('other.lua', 'return 1', 'native-child-device')
    finally:
        release.set()
    assert _wait_for_terminal_status(facade, task_id) == 'stopped'
    assert not any(thread.name == 'owned-native-child' for thread in enumerate_threads())


def test_native_stop_submission_cannot_race_with_returning_resources(tmp_path, monkeypatch):
    facade = _build_real_facade(tmp_path)
    code = 'while not shared.get_key("finish") do sleep(0.005) end; return 42'
    task_id = facade.run_script('stop-race.lua', code, 'stop-race-device')
    context = facade.state_mgr.get_run_context(task_id)
    tasker = context.maa.tasker
    original = tasker.post_stop
    entered, release = Event(), Event()

    def slow_post():
        entered.set()
        assert release.wait(3)
        return original()

    monkeypatch.setattr(tasker, 'post_stop', slow_post)
    with ThreadPoolExecutor(max_workers=1) as callers:
        stopping = callers.submit(facade.stop_script, task_id)
        try:
            assert entered.wait(1)
            context.runtime.global_shared_store.set_key('finish', True)
            Event().wait(0.15)
            assert context.maa.tasker is tasker
            assert facade.get_task_info(task_id).status == 'pending'
        finally:
            release.set()
        stopping.result(2)
    assert _wait_for_terminal_status(facade, task_id) == 'stopped'


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


def test_io_output_and_os_exit_reach_the_task_view(tmp_path):
    facade = _build_real_facade(tmp_path)
    task_id = facade.run_script('io-exit.lua', '''
        io.write("main")
        function worker() io.write("-child") end
        local child = thread.spawn("worker")
        assert(child:join(2))
        assert(child:error() == "", child:error())
        print("-line")
        io.write("tail")
        os.exit("expected exit")
        print("unreachable")
    ''', 'io-exit-device')
    assert _wait_for_terminal_status(facade, task_id) == 'stopped'
    output = facade.get_task_output(task_id)
    assert output.items == ['main-child-line', 'tail']
    assert output.total_lines == 2
    assert facade.get_task_info(task_id).error is None


def test_partial_io_output_is_visible_before_the_script_finishes(tmp_path):
    facade = _build_real_facade(tmp_path)
    task_id = facade.run_script('io-live.lua', '''
        io.write("progress")
        while not shared.get_key("finish") do sleep(0.005) end
        io.write("-done")
    ''', 'io-live-device')
    context = facade.state_mgr.get_run_context(task_id)
    try:
        deadline = time.monotonic() + 2
        while not facade.get_task_output(task_id).items:
            assert time.monotonic() < deadline
            Event().wait(0.005)
        before = facade.get_task_output(task_id)
        assert before.items == ['progress']
        assert facade.get_task_info(task_id).status == 'running'
    finally:
        context.runtime.global_shared_store.set_key('finish', True)
    assert _wait_for_terminal_status(facade, task_id) == 'success'
    after = facade.get_task_output(task_id)
    assert after.items == ['progress-done']
    assert after.version > before.version


def test_control_facade_run_script_executes_unsaved_in_memory_lua(tmp_path: Path) -> None:
    editor_dir = tmp_path / ".mluascript_web" / "lua"
    editor_dir.mkdir(parents=True)
    facade = _build_real_facade(tmp_path)

    task_id = facade.run_script(
        ".mluascript_web/lua/untitled.lua",
        "return 40 + 2",
        "ADB:unsaved",
    )
    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "success"
    assert task is not None
    assert task.result == 42
    assert not (editor_dir / "untitled.lua").exists()


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


def test_control_facade_stop_script_stops_real_lua_busy_loop(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_path = project_dir / "busy.lua"
    code = "local n = 0; while true do n = n + 1 end"
    script_path.write_text(code, encoding="utf-8")

    facade = _build_real_facade(tmp_path)

    task_id = facade.run_script("demo/busy.lua", code, "ADB:busy-stop")
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
