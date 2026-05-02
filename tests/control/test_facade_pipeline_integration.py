from __future__ import annotations

import time
from pathlib import Path

from mluascript.control.execution.manager import ExecutionManager
from mluascript.control.facade import ControlFacade
from mluascript.control.state.manager import StateManager
from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.shared.config.manager import load_config


class FakeTaskJob:
    def __init__(self, succeeded: bool = True, detail: object = None, delay: float = 0.0) -> None:
        self.succeeded = succeeded
        self._detail = detail
        self.delay = delay
        self.wait_called = False

    def wait(self) -> "FakeTaskJob":
        self.wait_called = True
        if self.delay > 0:
            time.sleep(self.delay)
        return self

    def get(self) -> object:
        return self._detail


class FakeTasker:
    def __init__(self, *, succeeded: bool = True, detail: object = None, delay: float = 0.0) -> None:
        self.post_task_calls: list[tuple[str, dict[str, object]]] = []
        self.task_job = FakeTaskJob(succeeded=succeeded, detail=detail, delay=delay)
        self.post_stop_called = False

    def post_task(self, entry: str, override: dict[str, object]) -> FakeTaskJob:
        self.post_task_calls.append((entry, override))
        return self.task_job

    def post_stop(self) -> FakeTaskJob:
        self.post_stop_called = True
        return FakeTaskJob(succeeded=True)


class FacadeWorkspaceManager(WorkspaceManager):
    pass


def _build_pipeline_facade(root_dir: Path, tasker: FakeTasker) -> ControlFacade:
    load_config(str(root_dir / "config.yaml"))
    facade = ControlFacade()
    facade.state_mgr = StateManager()
    workspace = FacadeWorkspaceManager(root_dir)
    facade.workspace_mgr = workspace
    exec_mgr = ExecutionManager()
    exec_mgr.script_use_case.state_manager = facade.state_mgr
    exec_mgr.pipeline_use_case.state_manager = facade.state_mgr
    exec_mgr.script_use_case.workspace_manager = workspace
    exec_mgr.pipeline_use_case.workspace_manager = workspace
    facade.exec_mgr = exec_mgr

    original_create = exec_mgr.integration_facade.create_pipeline_run

    def create_pipeline_run(locator, controller=None, connection_label=None):
        context = original_create(locator, controller=controller, connection_label=connection_label)
        context.maa.tasker = tasker
        return context

    exec_mgr.integration_facade.create_pipeline_run = create_pipeline_run  # type: ignore[method-assign]
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


def test_control_facade_run_pipeline_success_with_project_locator(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    resource_dir = project_dir / "resource"
    project_dir.mkdir()
    resource_dir.mkdir()
    (project_dir / "test.lua").write_text("print('hello')", encoding="utf-8")
    (resource_dir / "map.png").write_text("fake", encoding="utf-8")
    tasker = FakeTasker(succeeded=True, detail={"pipeline": True})

    facade = _build_pipeline_facade(tmp_path, tasker)
    task_id = facade.run_pipeline("entry.main", {"node": {"x": 1}}, "ADB:pipeline", "demo")

    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "success"
    assert task is not None
    assert task.kind == "pipeline"
    assert task.result == {"pipeline": True}
    assert tasker.post_task_calls == [("entry.main", {"entry.main": {"node": {"x": 1}}})]
    assert tasker.task_job.wait_called is True


def test_control_facade_run_pipeline_failed_when_tasker_reports_failure(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    resource_dir = project_dir / "resource"
    project_dir.mkdir()
    resource_dir.mkdir()
    (project_dir / "test.lua").write_text("print('hello')", encoding="utf-8")
    tasker = FakeTasker(succeeded=False, detail={"reason": "bad"})

    facade = _build_pipeline_facade(tmp_path, tasker)
    task_id = facade.run_pipeline("entry.main", {"node": {"x": 1}}, "ADB:pipeline", "demo")

    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "failed"
    assert task is not None
    assert task.error == "pipeline execution failed: entry.main"


def test_control_facade_stop_pipeline_marks_stopped_and_cleans_task(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    resource_dir = project_dir / "resource"
    project_dir.mkdir()
    resource_dir.mkdir()
    (project_dir / "test.lua").write_text("print('hello')", encoding="utf-8")
    tasker = FakeTasker(succeeded=True, detail={"pipeline": True}, delay=0.3)

    facade = _build_pipeline_facade(tmp_path, tasker)
    task_id = facade.run_pipeline("entry.main", {"node": {"x": 1}}, "ADB:pipeline", "demo")
    time.sleep(0.05)
    facade.stop_pipeline(task_id)

    status = _wait_for_terminal_status(facade, task_id)
    task = facade.get_task_info(task_id)

    assert status == "stopped"
    assert task is not None
    assert task.status == "stopped"
