from __future__ import annotations

from typing import Any

from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.tasks.models import TaskRequest
from mluascript.maa.tasks.runner import run_task
from mluascript.maa.tasks.stop import post_stop, stop_tasker
from mluascript.maa.types import MaaContextState, MaaPaths


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


class FakeStopJob:
    def __init__(self) -> None:
        self.wait_called = False

    def wait(self) -> "FakeStopJob":
        self.wait_called = True
        return self


class FakeTasker:
    def __init__(self) -> None:
        self.post_task_calls: list[tuple[str, dict[str, Any]]] = []
        self.post_stop_called = False
        self.task_job = FakeTaskJob(succeeded=True, detail={"ok": True})
        self.stop_job = FakeStopJob()

    def post_task(self, entry: str, override: dict[str, Any]) -> FakeTaskJob:
        self.post_task_calls.append((entry, override))
        return self.task_job

    def post_stop(self) -> FakeStopJob:
        self.post_stop_called = True
        return self.stop_job


def build_context(tasker: FakeTasker | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=__import__("pathlib").Path("."), resource_dir=__import__("pathlib").Path(".")),
        state=MaaContextState(connected=True, connection_label="ADB:demo"),
        tasker=tasker,
    )


def test_run_task_uses_tasker_and_wraps_result() -> None:
    tasker = FakeTasker()
    context = build_context(tasker)

    result = run_task(context, TaskRequest(entry="demo", override={"x": 1}))

    assert result.succeeded is True
    assert result.detail == {"ok": True}
    assert tasker.post_task_calls == [("demo", {"x": 1})]
    assert tasker.task_job.wait_called is True


def test_post_stop_waits_for_stop_job() -> None:
    tasker = FakeTasker()
    context = build_context(tasker)

    post_stop(context)

    assert tasker.post_stop_called is True
    assert tasker.stop_job.wait_called is True


def test_stop_tasker_marks_context_disconnected() -> None:
    tasker = FakeTasker()
    context = build_context(tasker)

    stop_tasker(context)

    assert tasker.post_stop_called is True
    assert context.state.connected is False
    assert context.state.connection_label is None
