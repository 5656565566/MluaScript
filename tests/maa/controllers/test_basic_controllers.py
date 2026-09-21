from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Any, cast

import pytest
from maa.controller import Controller

from mluascript.maa.controllers.base import controller_is_connected
from mluascript.maa.controllers.gesture import touch_down
from mluascript.maa.controllers.input import click, input_text, key_down
from mluascript.maa.controllers.screen import screencap
from mluascript.maa.errors import MaaConnectionError
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths


class FakeWaitable:
    def __init__(self, succeeded: bool = True) -> None:
        self.succeeded = succeeded
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
        self.connected = True
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

    def post_connection(self) -> FakeWaitable:
        return self._record("post_connection")

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


class FailedClickController(FakeController):
    def post_click(self, x: int, y: int) -> FakeWaitable:
        self.calls.append(("post_click", (x, y)))
        self.last_job = FakeWaitable(False)
        return self.last_job


class DisconnectingClickJob(FakeWaitable):
    def __init__(self, controller: FakeController) -> None:
        super().__init__(False)
        self._controller = controller

    def wait(self) -> "DisconnectingClickJob":
        self.wait_called = True
        self._controller.connected = False
        return self


class ReconnectJob(FakeWaitable):
    def __init__(self, controller: FakeController, succeeded: bool = True) -> None:
        super().__init__(succeeded)
        self._controller = controller

    def wait(self) -> "ReconnectJob":
        self.wait_called = True
        if self.succeeded:
            self._controller.connected = True
        return self


class RecoveringClickController(FakeController):
    def __init__(
        self,
        *,
        reconnect_succeeds: bool = True,
        screencap_succeeds: bool = True,
        first_click_disconnects: bool = True,
        replay_succeeds: bool = True,
    ) -> None:
        super().__init__()
        self._click_count = 0
        self._reconnect_succeeds = reconnect_succeeds
        self._screencap_succeeds = screencap_succeeds
        self._first_click_disconnects = first_click_disconnects
        self._replay_succeeds = replay_succeeds

    def post_click(self, x: int, y: int) -> FakeWaitable:
        self.calls.append(("post_click", (x, y)))
        self._click_count += 1
        if self._click_count == 1 and self._first_click_disconnects:
            self.last_job = DisconnectingClickJob(self)
        else:
            self.last_job = FakeWaitable(self._replay_succeeds)
        return self.last_job

    def post_connection(self) -> FakeWaitable:
        self.calls.append(("post_connection", ()))
        self.last_job = ReconnectJob(self, self._reconnect_succeeds)
        return self.last_job

    def post_screencap(self) -> FakeResultJob:
        self.calls.append(("post_screencap", ()))
        image = FakeImage(shape=(720, 1280, 3))
        self.last_job = FakeResultJob(self._screencap_succeeds, image)
        return self.last_job


class DisconnectingTouchController(FakeController):
    def post_touch_down(self, x: int, y: int, contact: int) -> FakeWaitable:
        self.calls.append(("post_touch_down", (x, y, contact)))
        self.last_job = DisconnectingClickJob(self)
        return self.last_job


class BlockingClickController(FakeController):
    def __init__(self) -> None:
        super().__init__()
        self.first_wait_started = Event()
        self.release_first_wait = Event()
        self._click_count = 0

    def post_click(self, x: int, y: int) -> FakeWaitable:
        self.calls.append(("post_click", (x, y)))
        self._click_count += 1
        if self._click_count == 1:
            controller = self

            class BlockingJob(FakeWaitable):
                def wait(self) -> "BlockingJob":
                    self.wait_called = True
                    controller.first_wait_started.set()
                    controller.release_first_wait.wait(1.0)
                    return self

            self.last_job = BlockingJob()
        else:
            self.last_job = FakeWaitable()
        return self.last_job


class MethodConnectedController:
    def __init__(self, connected: bool) -> None:
        self._connected = connected

    def connected(self) -> bool:
        return self._connected


def build_context(controller: FakeController | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
        controller=cast(Controller | None, controller),
    )


def test_click_waits_for_job() -> None:
    controller = FakeController()
    context = build_context(controller)

    result = click(context, 10, 20)

    assert result is True
    assert controller.calls == [("post_click", (10, 20))]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True


def test_click_raises_when_job_fails() -> None:
    controller = FailedClickController()
    context = build_context(controller)

    with pytest.raises(MaaConnectionError, match="Maa click failed"):
        click(context, 10, 20)

    assert controller.calls == [("post_click", (10, 20))]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True


def test_click_reconnects_and_replays_once_after_disconnect() -> None:
    controller = RecoveringClickController()
    context = build_context(controller)
    context.mark_connected("ADB:test")

    assert click(context, 10, 20) is True

    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_connection", ()),
        ("post_screencap", ()),
        ("post_click", (10, 20)),
    ]
    assert context.state.connected is True
    assert context.state.connection_label == "ADB:test"


def test_click_does_not_replay_when_reconnect_fails() -> None:
    controller = RecoveringClickController(reconnect_succeeds=False)
    context = build_context(controller)
    context.mark_connected("ADB:test")

    with pytest.raises(MaaConnectionError, match="Maa controller reconnect failed"):
        click(context, 10, 20)

    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_connection", ()),
    ]
    assert context.state.connected is False


def test_click_does_not_replay_when_reconnect_screencap_fails() -> None:
    controller = RecoveringClickController(screencap_succeeds=False)
    context = build_context(controller)

    with pytest.raises(MaaConnectionError, match="Maa screencap after reconnect failed"):
        click(context, 10, 20)

    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_connection", ()),
        ("post_screencap", ()),
    ]
    assert context.state.connected is False


def test_click_replay_failure_is_not_retried_again() -> None:
    controller = RecoveringClickController(replay_succeeds=False)
    context = build_context(controller)

    with pytest.raises(MaaConnectionError, match="Maa click failed after reconnect"):
        click(context, 10, 20)

    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_connection", ()),
        ("post_screencap", ()),
        ("post_click", (10, 20)),
    ]


def test_click_reconnects_before_submit_when_already_disconnected() -> None:
    controller = RecoveringClickController(first_click_disconnects=False)
    controller.connected = False
    context = build_context(controller)
    context.mark_connected("ADB:test")

    assert click(context, 10, 20) is True

    assert controller.calls == [
        ("post_connection", ()),
        ("post_screencap", ()),
        ("post_click", (10, 20)),
    ]


def test_touch_sequence_step_is_not_replayed_after_disconnect() -> None:
    controller = DisconnectingTouchController()
    context = build_context(controller)

    with pytest.raises(MaaConnectionError, match="Maa touch down failed"):
        touch_down(context, 10, 20)

    assert controller.calls == [("post_touch_down", (10, 20, 0))]


def test_controller_operations_are_serialized_while_waiting() -> None:
    controller = BlockingClickController()
    first_context = build_context(controller)
    second_context = build_context(controller)
    errors: list[Exception] = []
    second_started = Event()

    def run_click(context: MaaContext, x: int) -> None:
        try:
            if x == 30:
                second_started.set()
            click(context, x, 20)
        except Exception as exc:
            errors.append(exc)

    first = Thread(target=run_click, args=(first_context, 10))
    second = Thread(target=run_click, args=(second_context, 30))
    first.start()
    assert controller.first_wait_started.wait(1.0) is True
    second.start()
    assert second_started.wait(1.0) is True

    assert controller.calls == [("post_click", (10, 20))]
    controller.release_first_wait.set()
    first.join(1.0)
    second.join(1.0)

    assert errors == []
    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_click", (30, 20)),
    ]


def test_controller_connection_check_accepts_custom_controller_method() -> None:
    assert controller_is_connected(MethodConnectedController(True)) is True
    assert controller_is_connected(MethodConnectedController(False)) is False


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
