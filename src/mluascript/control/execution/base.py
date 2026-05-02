from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast

from mluascript.control.integration.facade import IntegrationFacade
from mluascript.control.state.manager import RunContext, StateManager, get_state_manager
from mluascript.control.state.models import TaskInfo, TaskKind
from mluascript.shared.logging import logger

TRunContext = TypeVar("TRunContext")


class BaseExecutionUseCase(ABC, Generic[TRunContext]):
    """统一封装执行任务的启动/停止模板流程"""

    task_kind: TaskKind

    def __init__(self, facade: IntegrationFacade) -> None:
        self.facade = facade
        self.state_manager: StateManager = get_state_manager()

    def start(self, *, target: str, log_message: str) -> str:
        for existing_task in self.state_manager.list_tasks():
            if existing_task.target == target and existing_task.status in ("pending", "running"):
                raise RuntimeError(f"设备 '{target}' 已有任务正在运行")

        logger.info(log_message)
        task = self.state_manager.create_task(
            self.task_kind,
            target,
            title=self.build_task_title(),
            summary=self.build_task_summary(),
        )
        self.state_manager.update_task_status(task.task_id, "running")

        try:
            context = self.create_context()
            self.bind_task_context(task, context)
            self.populate_start_info(task, context)
            self.do_start(task, context)
            return task.task_id
        except Exception as exc:
            logger.error(f"Failed to start {self.task_kind}: {exc}")
            self.state_manager.update_task_status(task.task_id, "failed", error=str(exc))
            self.unbind_task_context(task)
            raise

    def stop(self, task_id: str, *, log_message: str) -> None:
        logger.info(log_message)
        task = self.state_manager.get_task(task_id)
        if not task or task.kind != self.task_kind:
            return

        self.state_manager.update_task_status(task_id, "pending")
        try:
            context = self.resolve_task_context(task)
            if context is not None:
                self.do_stop(task, context)
            self.state_manager.update_task_status(task_id, "stopped")
        except Exception as exc:
            logger.error(f"Failed to stop {self.task_kind}: {exc}")
            self.state_manager.update_task_status(task_id, "failed", error=str(exc))
            raise
        finally:
            self.unbind_task_context(task)

    def bind_task_context(self, task: TaskInfo, context: TRunContext) -> None:
        self.state_manager.bind_run_context(task.task_id, cast(RunContext, context))

    def unbind_task_context(self, task: TaskInfo) -> None:
        self.state_manager.pop_run_context(task.task_id)

    def resolve_task_context(self, task: TaskInfo) -> TRunContext | None:
        context = self.state_manager.get_run_context(task.task_id)
        if context is None:
            return None
        return cast(TRunContext, context)

    def build_task_title(self) -> str | None:
        return None

    def build_task_summary(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def create_context(self) -> TRunContext:
        """创建运行上下文"""

    @abstractmethod
    def populate_start_info(self, task: TaskInfo, context: TRunContext) -> None:
        """写入任务启动时的上下文元数据"""

    @abstractmethod
    def do_start(self, task: TaskInfo, context: TRunContext) -> None:
        """执行具体启动逻辑"""

    @abstractmethod
    def do_stop(self, task: TaskInfo, context: TRunContext) -> None:
        """执行具体停止逻辑"""
