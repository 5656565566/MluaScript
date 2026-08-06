from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Dict, Optional

from mluascript.control.devices import get_device_facade
from mluascript.control.integration.facade import IntegrationFacade
from mluascript.control.integration.models import MaaPipelineRunContext, RunStatus
from mluascript.control.state.models import TaskInfo
from mluascript.control.workspace.manager import WorkspaceManager, get_workspace_manager
from mluascript.control.workspace.artifact_service import cleanup_artifact_runtime_dir
from mluascript.maa.tasks import TaskRequest, build_pipeline_override, run_task
from mluascript.runtime.threading.manager import RuntimeThreadManager

from .base import BaseExecutionUseCase


@dataclass(slots=True)
class PipelineStartRequest:
    entry: str
    override: Optional[Dict[str, Any]]
    target: str
    project_path: str
    title: str | None
    cleanup_dir: str | None


class PipelineExecutionUseCase(BaseExecutionUseCase[MaaPipelineRunContext]):
    """纯 Maa pipeline 执行用例"""

    task_kind = "pipeline"

    def __init__(
        self,
        facade: IntegrationFacade,
        thread_manager: RuntimeThreadManager | None = None,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        super().__init__(facade)
        self._current_request: PipelineStartRequest | None = None
        self.thread_manager = thread_manager or RuntimeThreadManager()
        self.workspace_manager = workspace_manager or get_workspace_manager()

    def start_pipeline(
        self,
        entry: str,
        override: Optional[Dict[str, Any]],
        target: str,
        project_path: str,
        *,
        title: str | None = None,
        cleanup_dir: str | None = None,
    ) -> str:
        self._current_request = PipelineStartRequest(
            entry=entry,
            override=override,
            target=target,
            project_path=project_path,
            title=title,
            cleanup_dir=cleanup_dir,
        )
        try:
            return self.start(
                target=target,
                log_message=f"Starting pipeline execution for {target}: entry={entry}",
            )
        finally:
            self._current_request = None

    def stop_pipeline(self, task_id: str) -> None:
        self.stop(task_id, log_message=f"Requesting stop for pipeline task {task_id}")

    def build_task_title(self) -> str | None:
        request = self._require_request()
        return request.title or request.entry

    def build_task_summary(self) -> dict[str, Any]:
        request = self._require_request()
        return {
            "entry": request.entry,
            "project_path": request.project_path,
            "target": request.target,
            "task_kind": "pipeline",
        }

    def create_context(self) -> MaaPipelineRunContext:
        request = self._require_request()
        locator = self.workspace_manager.build_pipeline_run_locator(request.project_path)
        locator.cleanup_dir = request.cleanup_dir
        
        device_facade = get_device_facade()
        session = device_facade._maa_facade.get_current_session()
        
        controller = session.controller if session else None
        label = device_facade.get_overview().connection.label

        return self.facade.create_pipeline_run(
            locator,
            controller=controller,
            connection_label=label,
        )

    def populate_start_info(self, task: TaskInfo, context: MaaPipelineRunContext) -> None:
        request = self._require_request()
        locator = context.locator
        self.state_manager.update_task_info(
            task.task_id,
            summary={
                "entry": request.entry,
                "target": task.target,
                "project_path": request.project_path,
                "project_root": locator.project_root,
                "resource_dir": locator.resource_dir,
                "working_dir": locator.working_dir,
            }
        )

    def do_start(self, task: TaskInfo, context: MaaPipelineRunContext) -> None:
        request = self._require_request()
        self.state_manager.update_task_info(
            task.task_id,
            summary={"override": request.override}
        )
        context.status = RunStatus.RUNNING

        def runner(cancel_event: Event) -> Any:
            _ = cancel_event
            try:
                result = self._execute_pipeline(context, request.entry, request.override)
                context.status = RunStatus.FINISHED
                self.state_manager.finish_task(task.task_id, "success", result=result)
                return result
            except Exception as exc:
                context.status = RunStatus.FAILED
                self.state_manager.finish_task(task.task_id, "failed", error=str(exc))
                raise
            finally:
                cleanup_artifact_runtime_dir(context.locator.cleanup_dir)

        host_task = self.thread_manager.spawn(runner, name=f"pipeline-run-{task.task_id[:8]}")
        context.host_task = host_task
        self.state_manager.update_task_info(
            task.task_id,
            summary={"host_task_id": host_task.task_id}
        )

    def do_stop(self, task: TaskInfo, context: MaaPipelineRunContext) -> None:
        self.facade.stop_pipeline_run(context)
        host_task = context.host_task
        if host_task is not None:
            host_task.cancel()
            host_task.join(0.2)
        if context.status is not RunStatus.STOPPED:
            context.status = RunStatus.STOPPED
        cleanup_artifact_runtime_dir(context.locator.cleanup_dir)
        self.state_manager.finish_task(task.task_id, "stopped")

    def _execute_pipeline(self, context: MaaPipelineRunContext, entry: str, override: Optional[Dict[str, Any]]) -> Any:
        request = TaskRequest(entry=entry, override=build_pipeline_override(entry, override))
        result = run_task(context.maa, request)
        if not result.succeeded:
            raise RuntimeError(f"pipeline execution failed: {entry}")
        return result.detail

    def _require_request(self) -> PipelineStartRequest:
        if self._current_request is None:
            raise RuntimeError("pipeline start request is missing")
        return self._current_request
