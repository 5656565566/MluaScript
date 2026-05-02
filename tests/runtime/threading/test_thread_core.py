from __future__ import annotations

import pytest
from lupa.lua54 import LuaRuntime

from mluascript.runtime.threading import RuntimeThreadManager, SharedValue, build_shared_exports, build_thread_exports


class _LuaDict(dict):
    def keys(self):
        return super().keys()

    def items(self):
        return super().items()



def test_shared_value_basic_operations() -> None:
    shared = SharedValue({"count": 1})

    assert shared.get() == {"count": 1}
    assert shared.get_key("count") == 1

    shared.set_key("count", 2)
    shared.update({"name": "mlua"})

    assert shared.get() == {"count": 2, "name": "mlua"}
    assert shared.size() == 2
    assert shared.is_nil() is False

    shared.clear()
    assert shared.is_nil() is True
    assert shared.size() == 0



def test_shared_value_list_operations() -> None:
    shared = SharedValue([1, 2])

    shared.append(3)
    shared.extend([4, 5])
    shared.set_key(2, 20)

    assert shared.get() == [1, 20, 3, 4, 5]
    assert shared.get_key(2) == 20



def test_shared_value_update_rejects_non_dict() -> None:
    shared = SharedValue({})

    with pytest.raises(TypeError):
        shared.update([1, 2, 3])



def test_shared_value_extend_rejects_non_list_argument() -> None:
    shared = SharedValue([])

    with pytest.raises(TypeError):
        shared.extend({"name": "runtime"})



def test_shared_value_append_rejects_non_list_storage() -> None:
    shared = SharedValue({})

    with pytest.raises(TypeError):
        shared.append("runtime")



def test_shared_value_set_key_extends_list_with_none_padding() -> None:
    shared = SharedValue(["first"])

    result = shared.set_key(3, "third")

    assert result == "third"
    assert shared.get() == ["first", None, "third"]



def test_shared_value_set_key_rejects_scalar_storage() -> None:
    shared = SharedValue("scalar")

    with pytest.raises(TypeError):
        shared.set_key("name", "runtime")



def test_shared_exports_value_factory() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_shared_exports(lua, SharedValue({}))

    view = exports.value(_LuaDict({"name": "runtime"}))

    assert view.get_key("name") == "runtime"
    view.set_key("name", "threading")
    assert view.get_key("name") == "threading"



def test_shared_exports_global_store_accessors() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    store = SharedValue({"name": "runtime"})
    exports = build_shared_exports(lua, store)

    assert exports.get_key("name") == "runtime"
    assert exports.get()["name"] == "runtime"

    exports.set_key("name", "threading")

    assert store.get_key("name") == "threading"



def test_runtime_thread_manager_spawn_and_cleanup() -> None:
    manager = RuntimeThreadManager()

    task = manager.spawn(lambda cancel_event: "done")

    assert task.join(1.0) is True
    assert task.result_value == "done"
    assert task.error_message == ""
    assert manager.get(task.task_id) is task
    assert manager.cleanup() == 1
    assert manager.get(task.task_id) is None



def test_runtime_thread_manager_cancel() -> None:
    manager = RuntimeThreadManager()

    task = manager.spawn(lambda cancel_event: cancel_event.wait(0.2))

    assert manager.cancel(task.task_id) is True
    assert task.join(1.0) is True
    assert task.is_cancelled is True



def test_thread_exports_expose_manager_state() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    task = manager.spawn(lambda cancel_event: "ok")
    assert task.join(1.0) is True

    listed = exports.list()
    info = exports.get(task.task_id)

    assert len(listed) == 1
    assert listed[0]["task_id"] == task.task_id
    assert info is not None
    assert info.id() == task.task_id
    assert info.is_done() is True



def test_thread_exports_get_missing_task_returns_none() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    assert exports.get("missing") is None



def test_thread_exports_cleanup_delegates_to_manager() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    task = manager.spawn(lambda cancel_event: "ok")
    assert task.join(1.0) is True

    assert exports.cleanup() == 1



def test_thread_exports_cancel_missing_task_returns_false() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    assert exports.cancel("missing") is False
