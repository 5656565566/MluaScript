from __future__ import annotations

from threading import Event, Thread
from typing import Any, Callable
from uuid import uuid4

from .task import RuntimeTask


class RuntimeThreadManager:
    """运行时后台线程管理器"""

    def __init__(self) -> None:
        self._tasks: dict[str, RuntimeTask] = {}

    def create_task(self, target: Callable[[Event], Any], *, name: str | None = None) -> RuntimeTask:
        task_id = uuid4().hex
        cancel_event = Event()
        task_ref: RuntimeTask | None = None

        def runner() -> None:
            nonlocal task_ref
            assert task_ref is not None
            try:
                result = target(cancel_event)
                task_ref.set_result(result)
            except Exception as exc:
                task_ref.set_error(str(exc))
            finally:
                task_ref.mark_finished()

        thread = Thread(target=runner, name=name or f"mlua-runtime-{task_id[:8]}", daemon=True)
        task_ref = RuntimeTask(task_id=task_id, thread=thread, cancel_event=cancel_event)
        self._tasks[task_id] = task_ref
        return task_ref

    def start_task(self, task: RuntimeTask) -> RuntimeTask:
        if not task.thread.is_alive() and not task.is_done:
            task.thread.start()
        return task

    def spawn(self, target: Callable[[Event], Any], *, name: str | None = None) -> RuntimeTask:
        task = self.create_task(target, name=name)
        return self.start_task(task)

    def get(self, task_id: str) -> RuntimeTask | None:
        return self._tasks.get(task_id)

    def list(self) -> list[RuntimeTask]:
        return list(self._tasks.values())

    def cancel(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        return task.cancel()

    def cleanup(self) -> int:
        finished_ids = [task_id for task_id, task in self._tasks.items() if task.is_done]
        for task_id in finished_ids:
            self._tasks.pop(task_id, None)
        return len(finished_ids)
