from __future__ import annotations

from contextlib import contextmanager
from threading import Lock, RLock
from typing import Callable, Generic, Iterator, Protocol, TypeVar, runtime_checkable

from mluascript.shared.logging import logger

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

    def post_connection(self) -> Waitable:
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

    def post_shell(self, cmd: str, timeout: int = 20000) -> ResultJob[str | bytes]:
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
    """兼容 Maa 普通 Controller 属性与 CustomController 方法两种连接接口"""
    connected = getattr(controller, "connected")
    if callable(connected):
        connected = connected()
    return bool(connected)


_CONTROLLER_OPERATION_LOCK_ATTR = "_mluascript_operation_lock"
_controller_operation_lock_guard = Lock()


def _controller_operation_lock(controller: object):
    lock = getattr(controller, _CONTROLLER_OPERATION_LOCK_ATTR, None)
    if lock is not None:
        return lock

    with _controller_operation_lock_guard:
        lock = getattr(controller, _CONTROLLER_OPERATION_LOCK_ATTR, None)
        if lock is None:
            lock = RLock()
            setattr(controller, _CONTROLLER_OPERATION_LOCK_ATTR, lock)
    return lock


def _require_bound_controller(context: MaaContext) -> MaaController:
    controller = context.controller
    if controller is None:
        raise MaaConnectionError("Device or control object not connected")
    return controller


def _query_controller_connected(context: MaaContext, controller: MaaController) -> bool:
    try:
        return controller_is_connected(controller)
    except Exception as exc:
        context.mark_connected(None)
        raise MaaConnectionError(f"Failed to query controller connection state: {exc}") from exc


def ensure_controller(context: MaaContext) -> MaaController:
    """确保当前上下文已绑定 controller"""
    controller = _require_bound_controller(context)
    if not _query_controller_connected(context, controller):
        context.mark_connected(None)
        raise MaaConnectionError("Device or control object disconnected")
    return controller


@contextmanager
def locked_controller(context: MaaContext) -> Iterator[MaaController]:
    """串行化 MluaScript 直接提交到同一 Maa Controller 的操作"""
    controller = _require_bound_controller(context)
    with _controller_operation_lock(controller):
        yield ensure_controller(context)


TJob = TypeVar("TJob", bound=Waitable)


def run_controller_operation(
    context: MaaContext,
    submit: Callable[[MaaController], TJob],
    *,
    operation: str,
    replay_after_reconnect: bool = False,
) -> TJob:
    """同步执行控制操作 明确断线时重连 并最多重投原操作一次"""
    controller = _require_bound_controller(context)
    connection_label = context.state.connection_label

    with _controller_operation_lock(controller):
        if not _query_controller_connected(context, controller):
            context.mark_connected(None)
            if not replay_after_reconnect:
                raise MaaConnectionError("Device or control object disconnected")
            _reconnect_controller(context, controller, connection_label, operation)

        job = submit(controller)
        try:
            wait_for(job, operation=operation)
            return job
        except MaaConnectionError:
            if not replay_after_reconnect or _query_controller_connected(context, controller):
                raise

            context.mark_connected(None)
            logger.warning(f"Maa {operation} failed after disconnect; reconnecting and replaying once")
            _reconnect_controller(context, controller, connection_label, operation)

            retry_job = submit(controller)
            try:
                wait_for(retry_job, operation=f"{operation} replay")
            except MaaConnectionError as retry_error:
                try:
                    if not controller_is_connected(controller):
                        context.mark_connected(None)
                except Exception:
                    context.mark_connected(None)
                raise MaaConnectionError(f"Maa {operation} failed after reconnect") from retry_error
            return retry_job


def _reconnect_controller(
    context: MaaContext,
    controller: MaaController,
    connection_label: str | None,
    operation: str,
) -> None:
    logger.warning(f"Maa controller disconnected during {operation}; reconnecting")
    wait_for(controller.post_connection(), operation="controller reconnect")
    wait_for(controller.post_screencap(), operation="screencap after reconnect")
    if not _query_controller_connected(context, controller):
        context.mark_connected(None)
        raise MaaConnectionError("Maa controller reconnect completed but controller is still disconnected")

    restored_label = connection_label
    if not restored_label:
        try:
            restored_label = str(controller.uuid or "").strip() or None
        except Exception:
            restored_label = None
    context.mark_connected(restored_label or "Maa controller")
    logger.info(f"Maa controller reconnected during {operation}")
