from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from mluascript.maa.controllers.input import click, input_text, key_down
from mluascript.maa.controllers.screen import screencap
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths


class FakeWaitable:
    def __init__(self) -> None:
        self.wait_called = False

    def wait(self) -> "FakeWaitable":
        self.wait_called = True
        return self


class FakeResultJob(FakeWaitable):
    def __init__(self, succeeded: bool, result: Any) -> None:
        super().__init__()
        self.succeeded = succeeded
        self._result = result

    def get(self) -> Any:
        return self._result


@dataclass
class FakeImage:
    shape: tuple[int, int, int]


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.last_job: FakeWaitable | FakeResultJob | None = None
        self.resolution = (1280, 720)
        self.uuid = "fake-controller"

    def _record(self, name: str, *args: Any, result: FakeWaitable | FakeResultJob | None = None) -> FakeWaitable | FakeResultJob:
        self.calls.append((name, args))
        self.last_job = result or FakeWaitable()
        return self.last_job

    def post_click(self, x: int, y: int) -> FakeWaitable:
        return self._record("post_click", x, y)

    def post_click_key(self, key: int) -> FakeWaitable:
        return self._record("post_click_key", key)

    def post_key_down(self, key: int) -> FakeWaitable:
        return self._record("post_key_down", key)

    def post_key_up(self, key: int) -> FakeWaitable:
        return self._record("post_key_up", key)

    def post_input_text(self, text: str) -> FakeWaitable:
        return self._record("post_input_text", text)

    def post_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> FakeWaitable:
        return self._record("post_swipe", x1, y1, x2, y2, duration)

    def post_touch_down(self, x: int, y: int, contact: int) -> FakeWaitable:
        return self._record("post_touch_down", x, y, contact)

    def post_touch_move(self, x: int, y: int, contact: int) -> FakeWaitable:
        return self._record("post_touch_move", x, y, contact)

    def post_touch_up(self, contact: int) -> FakeWaitable:
        return self._record("post_touch_up", contact)

    def post_scroll(self, dx: int, dy: int) -> FakeWaitable:
        return self._record("post_scroll", dx, dy)

    def post_screencap(self) -> FakeResultJob:
        image = FakeImage(shape=(720, 1280, 3))
        return cast(FakeResultJob, self._record("post_screencap", result=FakeResultJob(True, image)))

    def post_start_app(self, intent: str) -> FakeWaitable:
        return self._record("post_start_app", intent)

    def post_stop_app(self, intent: str) -> FakeWaitable:
        return self._record("post_stop_app", intent)


def build_context(controller: FakeController | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
        controller=controller,
    )


def test_click_waits_for_job() -> None:
    controller = FakeController()
    context = build_context(controller)

    result = click(context, 10, 20)

    assert result is True
    assert controller.calls == [("post_click", (10, 20))]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True


def test_key_down_waits_for_job() -> None:
    controller = FakeController()
    context = build_context(controller)

    result = key_down(context, 13)

    assert result is True
    assert controller.calls == [("post_key_down", (13,))]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True


def test_input_text_waits_for_job() -> None:
    controller = FakeController()
    context = build_context(controller)

    result = input_text(context, "hello")

    assert result is True
    assert controller.calls == [("post_input_text", ("hello",))]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True


def test_screencap_returns_image_when_job_succeeds() -> None:
    controller = FakeController()
    context = build_context(controller)

    image = screencap(context)

    assert image is not None
    assert image.shape == (720, 1280, 3)
    assert controller.calls == [("post_screencap", ())]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True
