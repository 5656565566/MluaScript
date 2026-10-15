from __future__ import annotations

from threading import Event, RLock, Thread, current_thread, local
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from .task import RuntimeTask
from ..exception import LuaExitException


class RuntimeThreadManager:
    """运行时后台线程管理器"""

    def __init__(self, *, max_tasks: int | None = None) -> None:
        self._tasks: dict[str, RuntimeTask] = {}
        self._lock = RLock()
        self._local = local()
        self._closed = False
        self._max_tasks = max_tasks

    @property
    def current_cancel_event(self) -> Event | None:
        return getattr(self._local, "cancel_event", None)

    def create_task(self, target: Callable[[Event], Any], *, name: str | None = None) -> RuntimeTask:
        task_id = uuid4().hex
        cancel_event = Event()
        task_ref: RuntimeTask | None = None

        def runner() -> None:
            nonlocal task_ref
            assert task_ref is not None
            self._local.cancel_event = cancel_event
            try:
                result = target(cancel_event)
                task_ref.set_result(result)
            except LuaExitException as exc:
                if not cancel_event.is_set():
                    task_ref.set_error(str(exc))
            except Exception as exc:
                task_ref.set_error(str(exc))
            finally:
                task_ref.mark_finished()
                del self._local.cancel_event

        thread = Thread(target=runner, name=name or f"mlua-runtime-{task_id[:8]}", daemon=True)
        task_ref = RuntimeTask(task_id=task_id, thread=thread, cancel_event=cancel_event)
        with self._lock:
            if self._closed:
                raise RuntimeError("Runtime thread manager has shut down")
            if self._max_tasks is not None and sum(not task.is_done for task in self._tasks.values()) >= self._max_tasks:
                raise RuntimeError(f"Runtime active thread limit reached ({self._max_tasks})")
            self._tasks[task_id] = task_ref
        return task_ref

    def start_task(self, task: RuntimeTask) -> RuntimeTask:
        with self._lock:
            if self._closed:
                raise RuntimeError("Runtime thread manager has shut down")
            if not task.thread.is_alive() and not task.is_done:
                try:
                    task.thread.start()
                except Exception as exc:
                    task.set_error(str(exc))
                    task.mark_finished()
                    raise
        return task

    def spawn(self, target: Callable[[Event], Any], *, name: str | None = None) -> RuntimeTask:
        task = self.create_task(target, name=name)
        return self.start_task(task)

    def get(self, task_id: str) -> RuntimeTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[RuntimeTask]:
        with self._lock:
            return list(self._tasks.values())

    def cancel(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        return task.cancel()

    def cleanup(self) -> int:
        with self._lock:
            finished_ids = [task_id for task_id, task in self._tasks.items() if task.is_done and not task.is_alive]
            for task_id in finished_ids:
                self._tasks.pop(task_id, None)
        return len(finished_ids)

    def shutdown(self, timeout: float = 2.0) -> bool:
        with self._lock:
            self._closed = True
            tasks = list(self._tasks.values())
            for task in tasks:
                task.cancel()
                if task.thread.ident is None:
                    task.mark_finished()
        deadline = monotonic() + max(0, timeout)
        for task in tasks:
            if task.thread.ident is not None and task.thread is not current_thread():
                task.thread.join(max(0, deadline - monotonic()))
        self.cleanup()
        return not self.list()
