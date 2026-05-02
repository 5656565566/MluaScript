from __future__ import annotations

from pathlib import Path

from mluascript.maa.connections.models import ConnectionInfo
from mluascript.maa.connections.session import ConnectionSession, ConnectionSessionStore
from mluascript.maa.facade import MaaFacade
from mluascript.maa.lifecycle.binding import bind_controller, unbind_controller
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths


class FakeController:
    def __init__(self, uuid: str = "controller-1") -> None:
        self.uuid = uuid


def build_context() -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
    )


def test_attach_session_updates_context_and_store() -> None:
    context = build_context()
    facade = MaaFacade(context)
    controller = FakeController("uuid-1")
    session = ConnectionSession(
        info=ConnectionInfo(kind="adb", label="ADB:1", meta={"address": "1"}),
        controller=controller,
    )

    facade.attach_session(session)

    assert facade.get_current_session() is session
    assert context.controller is controller
    assert context.state.connected is True
    assert context.state.connection_label == "ADB:1"


def test_clear_session_resets_context_and_store() -> None:
    context = build_context()
    facade = MaaFacade(context)
    session = ConnectionSession(info=ConnectionInfo(kind="adb", label="ADB:1"))
    facade.attach_session(session)

    facade.clear_session()

    assert facade.get_current_session() is None
    assert context.controller is None
    assert context.state.connected is False
    assert context.state.connection_label is None


def test_session_store_require_current_raises_when_missing() -> None:
    store = ConnectionSessionStore()

    try:
        store.require_current()
    except RuntimeError as exc:
        assert "No active Maa connection session" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_bind_and_unbind_controller_update_context_state() -> None:
    context = build_context()
    controller = FakeController("uuid-bind")

    bind_controller(context, controller)
    assert context.controller is controller
    assert context.state.connected is True
    assert context.state.connection_label == "uuid-bind"

    unbind_controller(context)
    assert context.controller is None
    assert context.state.connected is False
    assert context.state.connection_label is None
