from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Protocol

from mluascript.control.devices import get_device_facade
from mluascript.control.integration.facade import IntegrationFacade
from mluascript.control.integration.models import RunStatus, ScriptRunContext
from mluascript.maa.controllers.base import wait_for
from mluascript.control.state.models import TaskInfo
from mluascript.control.workspace.manager import WorkspaceManager, get_workspace_manager
from mluascript.runtime.exception import LuaExitException
from mluascript.runtime.threading.manager import RuntimeThreadManager
from mluascript.shared.logging import logger

from .base import BaseExecutionUseCase


class ScriptRuntime(Protocol):
    def execute(self, file_content: str) -> Any:
        ...


def reset_script_controller_state(context: ScriptRunContext) -> None:
    controller = context.maa.controller
    if controller is None:
        return

    contacts = context.maa.state.extras.get("active_touch_contacts")
    if isinstance(contacts, set):
        contacts_to_release = sorted(int(contact) for contact in contacts)
    else:
        contacts_to_release = []

    for contact in contacts_to_release:
        try:
            wait_for(controller.post_touch_up(contact))
        except Exception as exc:
            logger.debug(f"Skip touch contact reset: contact={contact}, reason={exc}")
    if isinstance(contacts, set):
        contacts.clear()

    try:
        wait_for(controller.post_inactive())
    except Exception as exc:
        logger.debug(f"Skip controller inactive reset: reason={exc}")


@dataclass(slots=True)
class ScriptStartRequest:
    script_path: str
    code: str
    target: str


class ScriptExecutionUseCase(BaseExecutionUseCase[ScriptRunContext]):
    """Lua 脚本执行用例"""

    task_kind = "script"

    def __init__(
        self,
        facade: IntegrationFacade,
        thread_manager: RuntimeThreadManager | None = None,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        super().__init__(facade)
        self._current_request: ScriptStartRequest | None = None
        self.thread_manager = thread_manager or RuntimeThreadManager()
        self.workspace_manager = workspace_manager or get_workspace_manager()

    def start_script(self, script_path: str, code: str, target: str) -> str:
        self._current_request = ScriptStartRequest(script_path=script_path, code=code, target=target)
        try:
            return self.start(
                target=target,
                log_message=f"Starting script execution for {target}: {script_path}",
            )
        finally:
            self._current_request = None

    def stop_script(self, task_id: str) -> None:
        self.stop(task_id, log_message=f"Requesting stop for task {task_id}")

    def build_task_title(self) -> str | None:
        request = self._require_request()
        return request.script_path

    def build_task_summary(self) -> dict[str, Any]:
        request = self._require_request()
        return {
            "script_path": request.script_path,
            "target": request.target,
            "task_kind": "script",
        }

    def create_context(self) -> ScriptRunContext:
        request = self._require_request()
        locator = self.workspace_manager.build_script_run_locator(request.script_path)

        device_facade = get_device_facade()
        session = device_facade._maa_facade.get_current_session()

        controller = session.controller if session else None
        label = device_facade.get_overview().connection.label

        return self.facade.create_script_run(
            locator,
            controller=controller,
            connection_label=label,
        )

    def populate_start_info(self, task: TaskInfo, context: ScriptRunContext) -> None:
        request = self._require_request()
        locator = context.locator
        self.state_manager.update_task_info(
            task.task_id,
            summary={
                "script_path": request.script_path,
                "target": task.target,
                "project_root": locator.project_root,
                "script_file": locator.script_file,
                "script_dir": locator.script_dir,
                "resource_dir": locator.resource_dir,
                "working_dir": locator.working_dir,
            },
            print_buffer=context.print_buffer,
            log_buffer=context.log_buffer,
        )

    def do_start(self, task: TaskInfo, context: ScriptRunContext) -> None:
        request = self._require_request()
        self.state_manager.update_task_info(
            task.task_id,
            summary={"code_size": len(request.code)}
        )
        context.status = RunStatus.RUNNING

        def runner(cancel_event: Event) -> Any:
            _ = cancel_event
            try:
                result = self._execute_script(context.runtime, request.code)
                self.state_manager.update_task_info(
                    task.task_id,
                    print_buffer=context.print_buffer,
                    log_buffer=context.log_buffer,
                )
                context.status = RunStatus.FINISHED
                self.state_manager.finish_task(task.task_id, "success", result=result)
                return result
            except LuaExitException:
                self.state_manager.update_task_info(
                    task.task_id,
                    print_buffer=context.print_buffer,
                    log_buffer=context.log_buffer,
                )
                context.status = RunStatus.STOPPED
                self.state_manager.finish_task(task.task_id, "stopped")
                return None
            except Exception as exc:
                self.state_manager.update_task_info(
                    task.task_id,
                    print_buffer=context.print_buffer,
                    log_buffer=context.log_buffer,
                )
                context.status = RunStatus.FAILED
                self.state_manager.finish_task(task.task_id, "failed", error=str(exc))
                raise
            finally:
                reset_script_controller_state(context)

        host_task = self.thread_manager.spawn(runner, name=f"script-run-{task.task_id[:8]}")
        context.host_task = host_task
        self.state_manager.update_task_info(
            task.task_id,
            summary={"host_task_id": host_task.task_id}
        )

    def do_stop(self, task: TaskInfo, context: ScriptRunContext) -> None:
        self.facade.cancel_script_run(context)
        host_task = context.host_task
        if host_task is not None:
            host_task.cancel()
            host_task.join(0.2)
        reset_script_controller_state(context)
        if context.status is not RunStatus.STOPPED:
            context.status = RunStatus.STOPPED
        self.state_manager.update_task_info(
            task.task_id,
            print_buffer=context.print_buffer,
            log_buffer=context.log_buffer,
        )
        self.state_manager.finish_task(task.task_id, "stopped")

    def _execute_script(self, runtime: ScriptRuntime, code: str) -> Any:
        return runtime.execute(code)

    def _require_request(self) -> ScriptStartRequest:
        if self._current_request is None:
            raise RuntimeError("script start request is missing")
        return self._current_request
