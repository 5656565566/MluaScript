from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from time import time
from typing import Any


@dataclass(slots=True)
class RuntimeTask:
    """运行时后台任务句柄"""

    task_id: str
    thread: Thread
    cancel_event: Event
    started_at: float = field(default_factory=time)
    done_event: Event = field(default_factory=Event)
    result_value: Any = None
    error_message: str = ""
    cancel_requested_at: float | None = None
    finished_at: float | None = None

    @property
    def is_alive(self) -> bool:
        return self.thread.is_alive()

    @property
    def is_done(self) -> bool:
        return self.done_event.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def id(self) -> str:
        return self.task_id

    def cancel(self) -> bool:
        if self.cancel_requested_at is None:
            self.cancel_requested_at = time()
        self.cancel_event.set()
        return True

    def join(self, timeout: float = 0) -> bool:
        if timeout <= 0:
            self.done_event.wait()
        else:
            self.done_event.wait(timeout=timeout)
        if not self.done_event.is_set() and not self.thread.is_alive():
            self.done_event.set()
        return self.done_event.is_set() or not self.thread.is_alive()

    def result(self) -> Any:
        return self.result_value

    def error(self) -> str:
        return self.error_message

    def set_result(self, value: Any) -> None:
        self.result_value = value

    def set_error(self, message: str) -> None:
        self.error_message = message

    def mark_finished(self) -> None:
        self.finished_at = time()
        self.done_event.set()

    def status(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "alive": self.is_alive,
            "done": self.is_done,
            "cancelled": self.is_cancelled,
            "started_at": self.started_at,
            "cancel_requested_at": self.cancel_requested_at,
            "finished_at": self.finished_at,
            "error": self.error_message,
        }
