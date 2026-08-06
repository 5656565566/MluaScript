from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from mluascript.control.execution.pipeline import PipelineExecutionUseCase
from mluascript.control.execution.script import ScriptExecutionUseCase, reset_script_controller_state
from mluascript.control.integration.facade import IntegrationFacade
from mluascript.control.integration.models import MaaPipelineRunContext, RunStatus, ScriptRunContext
from mluascript.control.state.manager import StateManager
from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.control.workspace.models import PipelineRunLocator, ScriptAsset, ScriptRunLocator, WorkspaceProject
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths
from mluascript.runtime.exception import LuaExitException
from mluascript.runtime.stopper import Stopper
from mluascript.runtime.threading.manager import RuntimeThreadManager
from mluascript.runtime.threading.task import RuntimeTask


class FakeRuntime:
    def __init__(self, *, result: Any = None, error: Exception | None = None, wait_for_cancel: bool = False) -> None:
        self.result = result
        self.error = error
        self.wait_for_cancel = wait_for_cancel
        self.executed_code: list[str] = []
        self.stopper: Stopper | None = None

    def execute(self, file_content: str) -> Any:
        self.executed_code.append(file_content)
        if self.wait_for_cancel:
            assert self.stopper is not None
            while not self.stopper.is_stop_requested:
                pass
            raise LuaExitException("stopped")
        if self.error is not None:
            raise self.error
        return self.result


class FakeTaskJob:
    def __init__(self, succeeded: bool = True, detail: Any = None) -> None:
        self.succeeded = succeeded
        self._detail = detail
        self.wait_called = False

    def wait(self) -> "FakeTaskJob":
        self.wait_called = True
        return self

    def get(self) -> Any:
        return self._detail


class FakeTasker:
    def __init__(self, *, succeeded: bool = True, detail: Any = None) -> None:
        self.post_task_calls: list[tuple[str, dict[str, Any]]] = []
        self.task_job = FakeTaskJob(succeeded=succeeded, detail=detail)

    def post_task(self, entry: str, override: dict[str, Any]) -> FakeTaskJob:
        self.post_task_calls.append((entry, override))
        return self.task_job


class FakeWaitable:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.wait_called = False

    def wait(self) -> "FakeWaitable":
        self.wait_called = True
        if self.error is not None:
            raise self.error
        return self


class FakeResetController:
    def __init__(self, *, failing_contacts: set[int] | None = None, inactive_error: Exception | None = None) -> None:
        self.failing_contacts = failing_contacts or set()
        self.inactive_error = inactive_error
        self.touch_up_calls: list[int] = []
        self.inactive_called = 0

    def post_touch_up(self, contact: int) -> FakeWaitable:
        self.touch_up_calls.append(contact)
        return FakeWaitable(error=RuntimeError(f"contact-{contact}")) if contact in self.failing_contacts else FakeWaitable()

    def post_inactive(self) -> FakeWaitable:
        self.inactive_called += 1
        return FakeWaitable(error=self.inactive_error)


class FakeWorkspaceManager(WorkspaceManager):
    def __init__(self) -> None:
        super().__init__(Path("."))

    def build_script_run_locator(
        self,
        script_path: str,
        *,
        allow_missing: bool = False,
        source_overrides: dict[str, str] | None = None,
    ) -> ScriptRunLocator:
        _ = allow_missing
        project = WorkspaceProject(
            project_id="demo",
            name="demo",
            root_dir="project/demo",
            scripts_dir="project/demo",
            resource_dir="project/demo/resource",
        )
        script = ScriptAsset(
            project_id="demo",
            name=Path(script_path).name,
            relative_path=script_path,
            absolute_path=f"project/demo/{script_path}",
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
            source_overrides=source_overrides or {},
        )

    def build_pipeline_run_locator(self, project_path: str) -> PipelineRunLocator:
        project = WorkspaceProject(
            project_id="demo",
            name="demo",
            root_dir=project_path,
            scripts_dir=project_path,
            resource_dir=f"{project_path}/resource",
        )
        return PipelineRunLocator(
            project=project,
            project_root=project.root_dir,
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
        )


class FakeIntegrationFacade(IntegrationFacade):
    def __init__(
        self,
        script_runtime_factory: Callable[[], FakeRuntime] | None = None,
        pipeline_tasker_factory: Callable[[], FakeTasker] | None = None,
    ) -> None:
        self.script_runtime_factory = script_runtime_factory or (lambda: FakeRuntime(result="ok"))
        self.pipeline_tasker_factory = pipeline_tasker_factory or (lambda: FakeTasker(succeeded=True, detail={"pipeline": True}))
        self.script_contexts: list[ScriptRunContext] = []
        self.pipeline_contexts: list[MaaPipelineRunContext] = []
        self.cancelled_script_contexts: list[ScriptRunContext] = []
        self.stopped_pipeline_contexts: list[MaaPipelineRunContext] = []

    def create_script_run(
        self,
        locator: ScriptRunLocator,
        controller: Any = None,
        connection_label: str | None = None,
    ) -> ScriptRunContext:
        _ = controller, connection_label
        runtime = self.script_runtime_factory()
        context = ScriptRunContext(
            run_id="script-run-1",
            runtime=cast(Any, runtime),
            maa=build_maa_context(),
            locator=locator,
            stopper=Stopper(),
            status=RunStatus.IDLE,
        )
        runtime.stopper = context.stopper
        self.script_contexts.append(context)
        return context

    def create_pipeline_run(
        self,
        locator: PipelineRunLocator,
        controller: Any = None,
        connection_label: str | None = None,
    ) -> MaaPipelineRunContext:
        _ = controller, connection_label
        context = MaaPipelineRunContext(
            run_id="pipeline-run-1",
            maa=build_maa_context(tasker=self.pipeline_tasker_factory()),
            locator=locator,
            status=RunStatus.IDLE,
        )
        self.pipeline_contexts.append(context)
        return context

    def cancel_script_run(self, context: ScriptRunContext) -> None:
        self.cancelled_script_contexts.append(context)
        context.stopper.request_stop()
        context.status = RunStatus.STOPPED

    def stop_pipeline_run(self, context: MaaPipelineRunContext) -> None:
        self.stopped_pipeline_contexts.append(context)
        context.status = RunStatus.STOPPED


class ImmediateRuntimeThreadManager(RuntimeThreadManager):
    def spawn(self, target, *, name: str | None = None) -> RuntimeTask:
        task = self.create_task(target, name=name)
        task.thread.run()
        return task


class DeferredRuntimeThreadManager(RuntimeThreadManager):
    def spawn(self, target, *, name: str | None = None) -> RuntimeTask:
        return self.create_task(target, name=name)


def build_maa_context(tasker: FakeTasker | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
        tasker=tasker,
    )


def make_script_use_case(
    state_manager: StateManager,
    facade: FakeIntegrationFacade | None = None,
    thread_manager: RuntimeThreadManager | None = None,
) -> ScriptExecutionUseCase:
    use_case = ScriptExecutionUseCase(
        facade or FakeIntegrationFacade(),
        thread_manager=thread_manager or RuntimeThreadManager(),
        workspace_manager=FakeWorkspaceManager(),
    )
    use_case.state_manager = state_manager
    return use_case


def make_pipeline_use_case(
    state_manager: StateManager,
    facade: FakeIntegrationFacade | None = None,
    thread_manager: RuntimeThreadManager | None = None,
) -> PipelineExecutionUseCase:
    use_case = PipelineExecutionUseCase(
        facade or FakeIntegrationFacade(),
        thread_manager=thread_manager or RuntimeThreadManager(),
        workspace_manager=FakeWorkspaceManager(),
    )
    use_case.state_manager = state_manager
    return use_case


def test_script_start_registers_context_and_locator_metadata() -> None:
    state_manager = StateManager()
    facade = FakeIntegrationFacade(script_runtime_factory=lambda: FakeRuntime(result="done"))
    use_case = make_script_use_case(state_manager, facade=facade, thread_manager=DeferredRuntimeThreadManager())

    task_id = use_case.start_script("scripts/demo.lua", "print('hi')", "ADB:1")

    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.kind == "script"
    assert task.status == "running"
    assert state_manager.has_run_context(task_id) is True

    context = cast(ScriptRunContext, state_manager.get_run_context(task_id))
    assert context is facade.script_contexts[0]
    assert context.locator.script_file == "project/demo/scripts/demo.lua"
    assert task.summary["project_root"] == "project/demo"
    assert task.summary["script_dir"] == "project/demo"
    assert task.summary["resource_dir"] == "project/demo/resource"
    assert task.summary["script_path"] == "scripts/demo.lua"
    assert task.summary["target"] == "ADB:1"
    assert context.host_task is not None
    assert context.host_task.is_done is False


def test_script_start_uses_explicit_task_title() -> None:
    state_manager = StateManager()
    facade = FakeIntegrationFacade(script_runtime_factory=lambda: FakeRuntime(result="done"))
    use_case = make_script_use_case(state_manager, facade=facade, thread_manager=DeferredRuntimeThreadManager())

    task_id = use_case.start_script(
        "runtime/tasks/package-demo/scripts/main.lua",
        "return 1",
        "LOCAL",
        title=".mluascript_web/builds/demo.mlspkg",
    )

    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.title == ".mluascript_web/builds/demo.mlspkg"


def test_script_background_success_updates_status_and_cleans_context() -> None:
    state_manager = StateManager()
    facade = FakeIntegrationFacade(script_runtime_factory=lambda: FakeRuntime(result={"ok": True}))
    use_case = make_script_use_case(state_manager, facade=facade, thread_manager=ImmediateRuntimeThreadManager())

    task_id = use_case.start_script("scripts/demo.lua", "return 1", "ADB:1")

    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.status == "success"
    assert task.result == {"ok": True}
    assert state_manager.get_run_context(task_id) is None
    context = facade.script_contexts[0]
    assert context.status is RunStatus.FINISHED


def test_script_stop_fetches_context_calls_facade_and_unbinds() -> None:
    state_manager = StateManager()
    facade = FakeIntegrationFacade(script_runtime_factory=lambda: FakeRuntime(wait_for_cancel=True))
    use_case = make_script_use_case(state_manager, facade=facade, thread_manager=RuntimeThreadManager())

    task_id = use_case.start_script("scripts/demo.lua", "while true do end", "ADB:1")
    context = cast(ScriptRunContext, state_manager.get_run_context(task_id))
    assert context is not None

    use_case.stop_script(task_id)
    assert context.host_task is not None
    context.host_task.join(1.0)

    assert len(facade.cancelled_script_contexts) == 1
    assert state_manager.get_run_context(task_id) is None
    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.status == "stopped"


def test_finish_task_updates_status_and_recycles_context() -> None:
    state_manager = StateManager()
    locator = FakeWorkspaceManager().build_pipeline_run_locator("project/demo")
    context = MaaPipelineRunContext(run_id="pipeline-run", maa=build_maa_context(), locator=locator)
    task = state_manager.create_task("pipeline", "ADB:finish")
    state_manager.bind_run_context(task.task_id, context)

    popped = state_manager.finish_task(task.task_id, "success", result={"done": True})

    assert popped is context
    assert state_manager.get_run_context(task.task_id) is None
    finished = state_manager.get_task(task.task_id)
    assert finished is not None
    assert finished.status == "success"
    assert finished.result == {"done": True}


def test_pipeline_start_registers_context_and_project_locator_metadata() -> None:
    state_manager = StateManager()
    tasker = FakeTasker(succeeded=True, detail={"pipeline": 1})
    facade = FakeIntegrationFacade(pipeline_tasker_factory=lambda: tasker)
    use_case = make_pipeline_use_case(state_manager, facade=facade, thread_manager=DeferredRuntimeThreadManager())

    task_id = use_case.start_pipeline("entry.main", {"node": {"x": 1}}, "ADB:2", "project/demo")

    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.kind == "pipeline"
    assert task.status == "running"
    assert state_manager.has_run_context(task_id) is True

    context = cast(MaaPipelineRunContext, state_manager.get_run_context(task_id))
    assert context is facade.pipeline_contexts[0]
    assert context.locator.project_root == "project/demo"
    assert task.summary["project_root"] == "project/demo"
    assert task.summary["resource_dir"] == "project/demo/resource"
    assert task.summary["entry"] == "entry.main"
    assert task.summary["project_path"] == "project/demo"
    assert context.host_task is not None
    assert context.host_task.is_done is False


def test_pipeline_background_success_updates_status_and_calls_real_task_runner() -> None:
    state_manager = StateManager()
    tasker = FakeTasker(succeeded=True, detail={"pipeline": True})
    facade = FakeIntegrationFacade(pipeline_tasker_factory=lambda: tasker)
    use_case = make_pipeline_use_case(state_manager, facade=facade, thread_manager=ImmediateRuntimeThreadManager())

    task_id = use_case.start_pipeline("entry.main", {"node": {"x": 1}}, "ADB:2", "project/demo")

    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.status == "success"
    assert task.result == {"pipeline": True}
    assert state_manager.get_run_context(task_id) is None
    assert tasker.post_task_calls == [("entry.main", {"entry.main": {"node": {"x": 1}}})]


def test_pipeline_stop_fetches_context_calls_facade_and_unbinds() -> None:
    state_manager = StateManager()
    tasker = FakeTasker(succeeded=True, detail={"pipeline": True})
    facade = FakeIntegrationFacade(pipeline_tasker_factory=lambda: tasker)
    use_case = make_pipeline_use_case(state_manager, facade=facade, thread_manager=DeferredRuntimeThreadManager())

    task_id = use_case.start_pipeline("entry.main", {"node": {"x": 1}}, "ADB:2", "project/demo")
    context = cast(MaaPipelineRunContext, state_manager.get_run_context(task_id))

    use_case.stop_pipeline(task_id)

    assert context is not None
    assert len(facade.stopped_pipeline_contexts) == 1
    assert state_manager.get_run_context(task_id) is None
    task = state_manager.get_task(task_id)
    assert task is not None
    assert task.status == "stopped"


def test_reset_script_controller_state_releases_common_contacts_and_inactivates() -> None:
    controller = FakeResetController()
    context = ScriptRunContext(
        run_id="script-run-1",
        runtime=cast(Any, FakeRuntime(result="ok")),
        maa=build_maa_context(),
        locator=FakeWorkspaceManager().build_script_run_locator("scripts/demo.lua"),
    )
    context.maa.controller = controller
    context.maa.state.extras["active_touch_contacts"] = {1, 3}

    reset_script_controller_state(context)

    assert controller.touch_up_calls == [1, 3]
    assert controller.inactive_called == 1
    assert context.maa.state.extras["active_touch_contacts"] == set()


def test_reset_script_controller_state_ignores_controller_reset_errors() -> None:
    controller = FakeResetController(failing_contacts={1, 3}, inactive_error=RuntimeError("inactive"))
    context = ScriptRunContext(
        run_id="script-run-2",
        runtime=cast(Any, FakeRuntime(result="ok")),
        maa=build_maa_context(),
        locator=FakeWorkspaceManager().build_script_run_locator("scripts/demo.lua"),
    )
    context.maa.controller = controller
    context.maa.state.extras["active_touch_contacts"] = {1, 3}

    reset_script_controller_state(context)

    assert controller.touch_up_calls == [1, 3]
    assert controller.inactive_called == 1
    assert context.maa.state.extras["active_touch_contacts"] == set()
