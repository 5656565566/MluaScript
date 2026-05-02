from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from mluascript.control.integration.models import MaaPipelineRunContext, ScriptRunContext
from mluascript.shared.logging import logger
from .models import SystemState, TaskInfo, TaskKind, TaskStatus

RunContext = ScriptRunContext | MaaPipelineRunContext


class StateManager:
    """维护全局执行任务列表、状态与运行上下文"""

    def __init__(self) -> None:
        self._state = SystemState()
        self._tasks: Dict[str, TaskInfo] = {}
        self._run_contexts: Dict[str, RunContext] = {}

    def get_state(self) -> SystemState:
        return self._state

    def create_task(
        self,
        kind: TaskKind,
        target: str,
        *,
        title: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> TaskInfo:
        task_id = str(uuid.uuid4())
        task = TaskInfo(
            task_id=task_id,
            kind=kind,
            status="pending",
            target=target,
            title=title,
            summary=dict(summary or {}),
        )
        self._tasks[task_id] = task
        self._state.active_tasks.append(task)
        logger.info(f"Task created: {task_id} ({kind} -> {target})")
        return task

    def list_tasks(self) -> list[TaskInfo]:
        return list(self._state.active_tasks)

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        task = self._tasks.pop(task_id, None)
        if task is None:
            return False
        self._run_contexts.pop(task_id, None)
        self._state.active_tasks = [item for item in self._state.active_tasks if item.task_id != task_id]
        logger.info(f"Task removed: {task_id}")
        return True

    def update_task_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None, result: Any = None) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = status
        if error is not None:
            task.error = error
        if result is not None:
            task.result = result

        logger.info(f"Task {task_id} status updated to: {status}")

    def update_task_info(
        self,
        task_id: str,
        *,
        summary: dict[str, Any] | None = None,
        log_buffer: list[Any] | None = None,
        print_buffer: list[Any] | None = None,
        capabilities: Any | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        if summary is not None:
            task.summary.update(summary)
        if log_buffer is not None:
            task.log_buffer = log_buffer
        if print_buffer is not None:
            task.print_buffer = print_buffer
        if capabilities is not None:
            task.capabilities = capabilities

    def bind_run_context(self, task_id: str, context: RunContext) -> None:
        self._run_contexts[task_id] = context

    def get_run_context(self, task_id: str) -> Optional[RunContext]:
        return self._run_contexts.get(task_id)

    def pop_run_context(self, task_id: str) -> Optional[RunContext]:
        return self._run_contexts.pop(task_id, None)

    def finish_task(self, task_id: str, status: TaskStatus, *, error: Optional[str] = None, result: Any = None) -> Optional[RunContext]:
        self.update_task_status(task_id, status, error=error, result=result)
        return self.pop_run_context(task_id)

    def has_run_context(self, task_id: str) -> bool:
        return task_id in self._run_contexts

    def update_connected_sessions(self, sessions: List[str]) -> None:
        self._state.connected_sessions = sessions


_global_state_manager = StateManager()


def get_state_manager() -> StateManager:
    return _global_state_manager
