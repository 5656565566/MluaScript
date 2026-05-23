from __future__ import annotations

from pathlib import Path

from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.utils.table_lua import lua_2_python


class _HostAPI:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.stop_checks = 0

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def notify(self, message: str) -> None:
        pass

    def check_stop(self) -> None:
        self.stop_checks += 1



def _make_engine() -> LuaEngine:
    engine = LuaEngine(Path("."), _HostAPI())
    engine.inject()
    return engine



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



def test_thread_spawn_subthread_reads_limited_globals_snapshot() -> None:
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
        "fifth": "nil",
    }, normalized



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
