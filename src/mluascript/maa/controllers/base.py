from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock, RLock
from time import monotonic, sleep
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
_CONTROLLER_RECONNECT_ATTR = "_mluascript_reconnect"
# 连接和首帧截图共享总时限；超时后保留原生作业，避免再次投递造成重叠。
_RECONNECT_TIMEOUT_SECONDS = 30.0


@dataclass
class _ReconnectState:
    job: Waitable | None = None
    capturing: bool = False
    waiting: bool = True


def _check_stop(context: MaaContext) -> None:
    check = context.state.extras.get("check_stop")
    if check is not None:
        check()


def controller_reconnect_pending(controller: object) -> bool:
    return getattr(controller, _CONTROLLER_RECONNECT_ATTR, None) is not None


def _reject_reconnecting(controller: object) -> None:
    if controller_reconnect_pending(controller):
        raise MaaConnectionError("Maa controller is reconnecting")


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
    _check_stop(context)
    _reject_reconnecting(controller)
    with _controller_operation_lock(controller):
        _check_stop(context)
        _reject_reconnecting(controller)
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

    reconnected = False
    pending = getattr(controller, _CONTROLLER_RECONNECT_ATTR, None)
    if pending is not None:
        if not replay_after_reconnect or pending.waiting or pending.job is None or not getattr(pending.job, "done", True):
            raise MaaConnectionError("Maa controller is reconnecting")
        _reconnect_controller(context, controller, connection_label, operation)
        reconnected = True

    for _ in range(2):
        _check_stop(context)
        _reject_reconnecting(controller)
        with _controller_operation_lock(controller):
            _check_stop(context)
            _reject_reconnecting(controller)
            if not _query_controller_connected(context, controller):
                context.mark_connected(None)
                if not replay_after_reconnect or reconnected:
                    raise MaaConnectionError("Device or control object disconnected")
            else:
                job = submit(controller)
                try:
                    wait_for(job, operation=f"{operation} replay" if reconnected else operation)
                    return job
                except MaaConnectionError as exc:
                    connected = _query_controller_connected(context, controller)
                    if not connected:
                        context.mark_connected(None)
                    if reconnected:
                        raise MaaConnectionError(f"Maa {operation} failed after reconnect") from exc
                    if not replay_after_reconnect or connected:
                        raise
        # 重连期间释放操作锁，新操作通过重连状态明确失败。
        _reconnect_controller(context, controller, connection_label, operation)
        reconnected = True
    raise MaaConnectionError(f"Maa {operation} failed after reconnect")


def _reconnect_controller(
    context: MaaContext,
    controller: MaaController,
    connection_label: str | None,
    operation: str,
) -> None:
    _check_stop(context)
    with _controller_operation_lock_guard:
        state = getattr(controller, _CONTROLLER_RECONNECT_ATTR, None)
        if state is not None:
            if state.waiting or state.job is None or not getattr(state.job, "done", True):
                raise MaaConnectionError("Maa controller is reconnecting")
            state.waiting = True
        else:
            state = _ReconnectState()
            setattr(controller, _CONTROLLER_RECONNECT_ATTR, state)
    completed = False
    try:
        logger.warning(f"Maa controller disconnected during {operation}; reconnecting")
        deadline = monotonic() + _RECONNECT_TIMEOUT_SECONDS
        if state.job is None:
            state.job = controller.post_connection()
        _wait_reconnect(context, state.job, deadline, "screencap after reconnect" if state.capturing else "controller reconnect")
        if not state.capturing:
            state.job = controller.post_screencap()
            state.capturing = True
            _wait_reconnect(context, state.job, deadline, "screencap after reconnect")
        completed = True
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
    finally:
        with _controller_operation_lock_guard:
            if completed or state.job is None or (getattr(state.job, "done", True) and not state.job.succeeded):
                setattr(controller, _CONTROLLER_RECONNECT_ATTR, None)
            else:
                state.waiting = False


def _wait_reconnect(context: MaaContext, job: Waitable, deadline: float, operation: str) -> None:
    # Maa Job 支持状态查询；仅提供 wait() 的旧控制器适配器保持原有同步契约。
    if hasattr(job, "done"):
        while not job.done:
            _check_stop(context)
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise MaaConnectionError(f"Maa {operation} timed out; native job is still pending")
            sleep(min(0.05, remaining))
    _check_stop(context)
    wait_for(job, operation=operation)
