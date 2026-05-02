from __future__ import annotations

from mluascript.runtime.stopper import Stopper
from mluascript.runtime.exception import LuaExitException


def test_stopper_initial_state() -> None:
    stopper = Stopper()

    assert stopper.is_stop_requested is False


def test_stopper_request_stop_and_reset() -> None:
    stopper = Stopper()

    stopper.request_stop()
    assert stopper.is_stop_requested is True

    stopper.reset()
    assert stopper.is_stop_requested is False


def test_stopper_check_raises_after_stop_request() -> None:
    stopper = Stopper()
    stopper.request_stop()

    try:
        stopper.check()
    except LuaExitException as exc:
        assert "Execution stopped by host" in str(exc)
    else:
        raise AssertionError("expected LuaExitException")
