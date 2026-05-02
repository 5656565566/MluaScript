from __future__ import annotations

from pathlib import Path
from typing import cast

from mluascript.control.integration.models import MaaPipelineRunContext, RunStatus, ScriptRunContext
from mluascript.control.integration.stop import cancel_script_run, stop_pipeline_run
from mluascript.control.workspace.models import PipelineRunLocator, ScriptAsset, ScriptRunLocator, WorkspaceProject
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths
from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.stopper import Stopper


class FakeStopJob:
    def __init__(self) -> None:
        self.wait_called = False

    def wait(self) -> "FakeStopJob":
        self.wait_called = True
        return self


class FakeTasker:
    def __init__(self) -> None:
        self.post_stop_called = False
        self.stop_job = FakeStopJob()

    def post_stop(self) -> FakeStopJob:
        self.post_stop_called = True
        return self.stop_job


class FakeRuntime:
    pass


def build_maa_context(tasker: FakeTasker | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(connected=True, connection_label="ADB:test"),
        tasker=tasker,
    )


def build_script_locator() -> ScriptRunLocator:
    project = WorkspaceProject(
        project_id="demo",
        name="demo",
        root_dir="project/demo",
        scripts_dir="project/demo",
        resource_dir="project/demo/resource",
    )
    script = ScriptAsset(
        project_id="demo",
        name="test.lua",
        relative_path="test.lua",
        absolute_path="project/demo/test.lua",
        mtime=0.0,
    )
    return ScriptRunLocator(
        project=project,
        script=script,
        project_root=project.root_dir,
        script_file=script.absolute_path,
        script_dir="project/demo",
        working_dir=project.root_dir,
        resource_dir=project.resource_dir,
    )


def build_pipeline_locator() -> PipelineRunLocator:
    project = WorkspaceProject(
        project_id="demo",
        name="demo",
        root_dir="project/demo",
        scripts_dir="project/demo",
        resource_dir="project/demo/resource",
    )
    return PipelineRunLocator(
        project=project,
        project_root=project.root_dir,
        working_dir=project.root_dir,
        resource_dir=project.resource_dir,
    )


def test_cancel_script_run_requests_runtime_stop_and_stops_maa() -> None:
    tasker = FakeTasker()
    maa = build_maa_context(tasker)
    context = ScriptRunContext(
        run_id="script-run",
        runtime=cast(LuaEngine, FakeRuntime()),
        maa=maa,
        locator=build_script_locator(),
        stopper=Stopper(),
        status=RunStatus.RUNNING,
    )

    cancel_script_run(context)

    assert context.status is RunStatus.STOPPED
    assert context.stopper.is_stop_requested is True
    assert tasker.post_stop_called is True
    assert tasker.stop_job.wait_called is True
    assert maa.state.connected is False
    assert maa.state.connection_label is None


def test_stop_pipeline_run_stops_maa_only() -> None:
    tasker = FakeTasker()
    maa = build_maa_context(tasker)
    context = MaaPipelineRunContext(
        run_id="pipeline-run",
        maa=maa,
        locator=build_pipeline_locator(),
        status=RunStatus.RUNNING,
    )

    stop_pipeline_run(context)

    assert context.status is RunStatus.STOPPED
    assert tasker.post_stop_called is True
    assert tasker.stop_job.wait_called is True
    assert maa.state.connected is False
    assert maa.state.connection_label is None
