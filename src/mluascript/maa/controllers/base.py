from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable

from ..errors import MaaConnectionError
from ..lifecycle.runtime import MaaContext


@runtime_checkable
class Waitable(Protocol):
    @property
    def succeeded(self) -> bool:
        ...

    def wait(self) -> object:
        ...


TWaitSelf = TypeVar("TWaitSelf", bound="WaitableSelf")


@runtime_checkable
class WaitableSelf(Protocol):
    def wait(self: TWaitSelf) -> TWaitSelf:
        ...


TResult_co = TypeVar("TResult_co", covariant=True)


@runtime_checkable
class ResultJob(Protocol, Generic[TResult_co]):
    @property
    def succeeded(self) -> bool:
        ...

    def wait(self) -> "ResultJob[TResult_co]":
        ...

    def get(self) -> TResult_co:
        ...


@runtime_checkable
class SupportsShape(Protocol):
    @property
    def shape(self) -> tuple[int, int] | tuple[int, int, int]:
        ...


@runtime_checkable
class MaaController(Protocol):
    @property
    def resolution(self) -> tuple[int, int]:
        ...

    @property
    def uuid(self) -> str:
        ...

    def post_click(self, x: int, y: int) -> Waitable:
        ...

    def post_click_key(self, key: int) -> Waitable:
        ...

    def post_key_down(self, key: int) -> Waitable:
        ...

    def post_key_up(self, key: int) -> Waitable:
        ...

    def post_input_text(self, text: str) -> Waitable:
        ...

    def post_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> Waitable:
        ...

    def post_touch_down(self, x: int, y: int, contact: int) -> Waitable:
        ...

    def post_touch_move(self, x: int, y: int, contact: int) -> Waitable:
        ...

    def post_touch_up(self, contact: int) -> Waitable:
        ...

    def post_scroll(self, dx: int, dy: int) -> Waitable:
        ...

    def post_screencap(self) -> ResultJob[SupportsShape]:
        ...

    def post_start_app(self, intent: str) -> Waitable:
        ...

    def post_stop_app(self, intent: str) -> Waitable:
        ...

    def post_shell(self, command: str) -> ResultJob[str | bytes]:
        ...

    def post_inactive(self) -> Waitable:
        ...


def wait_for(job: Waitable, *, operation: str = "controller operation") -> None:
    job.wait()
    if not job.succeeded:
        job_id = getattr(job, "job_id", None)
        detail = f" (job_id={job_id})" if job_id is not None else ""
        raise MaaConnectionError(f"Maa {operation} failed{detail}")


def wait_for_result(job: ResultJob[TResult_co]) -> ResultJob[TResult_co]:
    return job.wait()


def controller_is_connected(controller: object) -> bool:
    """兼容 Maa 普通 Controller 属性与 CustomController 方法两种连接接口。"""
    connected = getattr(controller, "connected")
    if callable(connected):
        connected = connected()
    return bool(connected)


def ensure_controller(context: MaaContext) -> MaaController:
    """确保当前上下文已绑定 controller"""
    controller = context.controller
    if controller is None:
        raise MaaConnectionError("Device or control object not connected")
    try:
        connected = controller_is_connected(controller)
    except Exception as exc:
        context.mark_connected(None)
        raise MaaConnectionError(f"Failed to query controller connection state: {exc}") from exc
    if not connected:
        context.mark_connected(None)
        raise MaaConnectionError("Device or control object disconnected")
    return controller
