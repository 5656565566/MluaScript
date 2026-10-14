from __future__ import annotations

from pathlib import Path

import pytest

from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.output_buffer import TaskOutputBuffer
from mluascript.runtime.utils.table_lua import lua_2_python


class _HostAPI:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.stop_checks = 0
        self.output = TaskOutputBuffer()

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def print(self, message: str) -> None:
        self.output.append(message)

    def notify(self, message: str) -> None:
        pass

    def check_stop(self) -> None:
        self.stop_checks += 1

    def clear_output(self) -> None:
        self.output.clear()

    def set_output_limit(self, max_lines: int) -> int:
        return self.output.set_max_lines(max_lines)

    def get_output_limit(self) -> int:
        return self.output.max_lines



def _make_engine() -> LuaEngine:
    engine = LuaEngine(Path("."), _HostAPI())
    engine.inject()
    return engine


@pytest.mark.parametrize("setup, expression, expected", [
    ("local value = 42", "value", 42),
    ("local value = nil", "value == nil", True),
    ("local value = false", "value == false", True),
    (r'local value = "中文\0\255"', r'value == "中文\0\255"', True),
    ("local value = {[false] = 42, [7] = 8}", "value[false] + value[7]", 50),
    ("local value = {nested = {answer = 42}}", "value.nested.answer", 42),
    ("local value = {}; value.self = value", "value.self == value", True),
    ("local answer = 42; local value = function() return answer end", "value()", 42),
    ("local value; value = function(n) if n == 0 then return 1 end return n * value(n - 1) end", "value(5)", 120),
])
def test_thread_spawn_copies_closure_upvalues(setup, expression, expected) -> None:
    engine = _make_engine()
    result = engine.execute(f'''
        {setup}
        function captured_target() return {expression} end
        local task = thread.spawn("captured_target")
        assert(task:join(2))
        return task:result(), task:error()
    ''')
    assert result == (expected, "")


def test_thread_spawn_copies_helpers_and_preserves_shared_upvalue_cells() -> None:
    engine = _make_engine()
    result = engine.execute('''
        local count = 40
        function increment() count = count + 1 end
        function read_count() return count end
        function captured_target()
            increment(); increment()
            return read_count()
        end
        local task = thread.spawn("captured_target")
        assert(task:join(2))
        return task:result(), task:error(), count
    ''')
    assert result == (42, "", 40)


def test_thread_spawn_snapshot_is_captured_before_main_changes() -> None:
    engine = _make_engine()
    result = engine.execute('''
        local value = {answer = 42}
        function captured_target()
            while not shared.get_key("ready") do sleep(0.01) end
            local answer = value.answer
            value.answer = 99
            return answer
        end
        local task = thread.spawn("captured_target")
        value.answer = 7
        shared.set_key("ready", true)
        assert(task:join(2))
        return task:result(), task:error(), value.answer
    ''')
    assert result == (42, "", 7)


@pytest.mark.parametrize("value", ["print", "math.abs", "coroutine.create(function() end)", "setmetatable({}, {})"])
def test_thread_spawn_rejects_unsafe_upvalues_before_starting(value) -> None:
    engine = _make_engine()
    result = engine.execute(f'''
        local value = {value}
        function captured_target() return value end
        local ok, err = pcall(thread.spawn, "captured_target")
        return ok, tostring(err)
    ''')
    assert result[0] is False
    assert "upvalue" in result[1]
    assert engine.thread_manager.list() == []


def test_thread_spawn_restores_environment_when_it_is_not_first_upvalue() -> None:
    engine = _make_engine()
    result = engine.execute('''
        local value = 40
        function captured_target() return value + math.abs(-2) end
        local task = thread.spawn("captured_target")
        assert(task:join(2))
        return task:result(), task:error()
    ''')
    assert result == (42, "")



def test_thread_spawn_returns_task_handle() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_return_handle()
            return 123
        end

        local task = thread.spawn("thread_test_return_handle")
        task:join(1.0)
        return {
            debug_task_id = task:id(),
            debug_result = task:result(),
            debug_error = task:error(),
            debug_status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert isinstance(normalized.get("debug_task_id"), str), normalized
    assert normalized.get("debug_result") == 123, normalized
    assert normalized.get("debug_error") in ("", None), normalized



def test_thread_spawn_passes_args_to_subthread() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_args(a, b, c, d)
            return a + b + c + d
        end

        local task = thread.spawn(
            "thread_test_args",
            nil,
            3,
            4,
            5,
            6
        )
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == 18, normalized



def test_thread_spawn_passes_context_id() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_context_id()
            shared.set_key("inside", true)
            return 1
        end

        local task = thread.spawn("thread_test_context_id")
        task:join(1.0)
        return {
            debug_task_id = task:id(),
            debug_shared = shared.get_key("inside"),
            debug_result = task:result(),
            debug_error = task:error(),
            debug_status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert isinstance(normalized.get("debug_task_id"), str), normalized
    assert normalized.get("debug_shared") is True, normalized
    assert normalized.get("debug_result") == 1, normalized
    assert normalized.get("debug_error") in ("", None), normalized



def test_thread_spawn_subthread_reads_values_and_global_functions_snapshot() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        safe_number = 42
        safe_text = "hello"
        safe_bool = true
        hidden_fn = function() return "x" end
        _private_value = "should_not_copy"

        function thread_test_globals_snapshot()
            return safe_number, safe_text, safe_bool, _private_value, type(hidden_fn)
        end

        local task = thread.spawn("thread_test_globals_snapshot")
        task:join(1.0)
        local a, b, c, _, e = task:result()
        return {
            debug_result = {
                first = a,
                second = b,
                third = c,
                fifth = e,
            },
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == {
        "first": 42,
        "second": "hello",
        "third": True,
        "fifth": "function",
    }, normalized


def test_thread_spawn_subthread_calls_nested_global_helpers() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_leaf_helper(value)
            return value + 1
        end

        function thread_test_middle_helper(value)
            return thread_test_leaf_helper(value) * 2
        end

        function thread_test_nested_helpers()
            return thread_test_middle_helper(20)
        end

        local task = thread.spawn("thread_test_nested_helpers")
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == 42, normalized


def test_thread_spawn_subthread_calls_encoded_global_helper() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function _E6_88_98_E6_96_97_E6_96_B9_E6_A1_88()
            return "battle-plan-ready"
        end

        function thread_test_encoded_helper()
            return _E6_88_98_E6_96_97_E6_96_B9_E6_A1_88()
        end

        local task = thread.spawn("thread_test_encoded_helper")
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == "battle-plan-ready", normalized


def test_thread_spawn_global_helper_uses_dynamic_namespace() -> None:
    engine = _make_engine()
    engine.register_namespace(
        "maa",
        lambda _: {
            "click": lambda x, y: x + y,
        },
    )

    result = engine.execute(
        '''
        function thread_test_click_helper()
            return maa.click(20, 22)
        end

        function thread_test_dynamic_namespace_helper()
            return thread_test_click_helper()
        end

        local task = thread.spawn("thread_test_dynamic_namespace_helper")
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == 42, normalized


def test_thread_spawn_subthread_calls_recursive_global_helper() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_factorial(value)
            if value <= 1 then
                return 1
            end
            return value * thread_test_factorial(value - 1)
        end

        function thread_test_recursive_helper()
            return thread_test_factorial(5)
        end

        local task = thread.spawn("thread_test_recursive_helper")
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") == 120, normalized


def test_thread_spawn_restores_injected_functions_with_local_upvalues() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_result_helper()
            local items = {
                { text = "enemy spotted" },
            }
            return result_contains_text(items, "enemy")
        end

        local task = thread.spawn("thread_test_result_helper")
        task:join(1.0)
        return {
            debug_result = task:result(),
            debug_error = task:error(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_result") is True, normalized



def test_thread_spawn_cancel_flow() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_cancel_flow()
            while not is_cancelled() do
                sleep(0.01)
            end
            return "cancelled"
        end

        local task = thread.spawn("thread_test_cancel_flow")
        task:cancel()
        task:join(1.0)
        return {
            debug_cancelled = task:is_cancelled(),
            debug_result = task:result(),
            debug_error = task:error(),
            debug_status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_cancelled") is True, normalized
    assert normalized.get("debug_result") == "cancelled", normalized
    assert normalized.get("debug_error") in ("", None), normalized



def test_thread_spawn_force_stop_marks_cancellation_intent() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_force_stop_busy_loop()
            local n = 0
            while true do
                n = n + 1
            end
        end

        local task = thread.spawn("thread_test_force_stop_busy_loop")
        sleep(0.2)
        local cancel_result = task:cancel()
        local join_result = task:join(0.05)
        local status = task:status()
        return {
            debug_cancel_result = cancel_result,
            debug_join_result = join_result,
            debug_cancelled = task:is_cancelled(),
            debug_done = task:is_done(),
            debug_alive = task:is_alive(),
            debug_result = task:result(),
            debug_error = task:error(),
            debug_status = status,
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_cancel_result") is True, normalized
    assert normalized.get("debug_cancelled") is True, normalized
    assert normalized.get("debug_status", {}).get("cancelled") is True, normalized
    assert normalized.get("debug_status", {}).get("cancel_requested_at") is not None, normalized
    assert normalized.get("debug_result") is None, normalized
    assert normalized.get("debug_error") in ("", None), normalized
    assert normalized.get("debug_join_result") in (True, False), normalized



def test_thread_get_returns_task_handle() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_get_handle()
            return 456
        end

        local task = thread.spawn("thread_test_get_handle")
        task:join(1.0)
        local fetched = thread.get(task:id())
        return {
            debug_fetched_result = fetched:result(),
            debug_fetched_done = fetched:is_done(),
            debug_fetched_error = fetched:error(),
            debug_fetched_status = fetched:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_fetched_result") == 456, normalized
    assert normalized.get("debug_fetched_done") is True, normalized
    assert normalized.get("debug_fetched_error") in ("", None), normalized



def test_thread_spawn_captures_error() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_error()
            error("boom")
        end

        local task = thread.spawn("thread_test_error")
        task:join(1.0)
        return {
            debug_error = task:error(),
            debug_result = task:result(),
            debug_status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert "boom" in str(normalized.get("debug_error", "")), normalized
    assert normalized.get("debug_result") is None, normalized


def test_thread_spawn_reports_subthread_chunk_failure() -> None:
    engine = _make_engine()

    result = engine.execute(
        '''
        function thread_test_bad_chunk()
            local broken = load("local x =")
            return broken()
        end

        local task = thread.spawn("thread_test_bad_chunk")
        task:join(1.0)
        return {
            debug_error = task:error(),
            debug_result = task:result(),
            debug_status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized.get("debug_result") is None, normalized
    assert "attempt to call a nil value" in str(normalized.get("debug_error", "")), normalized
