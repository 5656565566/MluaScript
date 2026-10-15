from pathlib import Path
from threading import Event
from time import monotonic
import gc
import weakref

import pytest

from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.stopper import Stopper


class Host:
    def __init__(self):
        self.stopper = Stopper()

    def check_stop(self): self.stopper.check()
    def print(self, message): pass
    def log(self, level, message): pass
    def notify(self, message): pass
    def clear_output(self): pass
    def set_output_limit(self, value): return value
    def get_output_limit(self): return 300


@pytest.fixture
def engine():
    host = Host()
    runtime = LuaEngine(Path('.'), host)
    yield runtime
    host.stopper.request_stop()
    for task in runtime.thread_manager.list():
        assert task.join(2)


@pytest.mark.parametrize('body', ['while true do end', 'sleep(60)'])
def test_cancel_stops_computation_and_sleep_without_stopping_sibling(engine, body):
    task = engine.execute(f'function worker() {body} end; return thread.spawn("worker")')
    task.cancel()
    assert task.join(1)
    assert task.is_cancelled()
    assert not task.is_alive()
    assert engine.execute('function other() return 42 end; local t = thread.spawn("other"); assert(t:join(2)); return t:result()') == 42


def test_join_can_be_cancelled_by_its_calling_task(engine):
    blocked = Event()
    engine.register_namespace('probe', lambda lua: {'block': lambda: blocked.wait(3)})
    try:
        task = engine.execute('''
            function blocked_worker() probe.block() end
            function waiting_worker()
                local t = thread.spawn("blocked_worker")
                shared.set_key("joining", true)
                t:join()
            end
            return thread.spawn("waiting_worker")
        ''')
        deadline = monotonic() + 2
        while not engine.global_shared_store.get_key('joining'):
            assert monotonic() < deadline
            Event().wait(0.005)
        task.cancel()
        assert task.join(1)
    finally:
        blocked.set()


@pytest.mark.parametrize('expression, read, expected', [
    ('{nested = {answer = 42}}', 'return result.nested.answer', 42),
    ('(function() local t = {}; t.self = t; return t end)()', 'return result.self == result', True),
    ('{[false] = "bool", [1] = "number"}', 'return result[false], result[1]', ('bool', 'number')),
    ('"中文\\0\\255"', 'return result == "中文\\0\\255"', True),
])
def test_results_are_restored_in_the_calling_runtime(engine, expression, read, expected):
    assert engine.execute(f'''
        function worker() return {expression} end
        local task = thread.spawn("worker")
        assert(task:join(2))
        local result = task:result()
        {read}
    ''') == expected


def test_multiple_results_preserve_nil_slots_and_shared_tables(engine):
    assert engine.execute('''
        function worker() local t = {answer = 42}; return nil, t, false, t, nil end
        local task = thread.spawn("worker")
        assert(task:join(2))
        local result = table.pack(task:result())
        return result.n, result[2].answer, result[3], result[2] == result[4], result[5] == nil
    ''') == (5, 42, False, True, True)


def test_returning_an_inherited_global_table_remains_a_lua_table(engine):
    assert engine.execute('''
        payload = {nested = {answer = 42}}
        function worker() return payload end
        local task = thread.spawn("worker")
        assert(task:join(2))
        assert(task:error() == "", task:error())
        local result = task:result()
        return type(result), type(result.nested), result.nested.answer
    ''') == ('table', 'table', 42)


def test_global_tables_share_the_closure_graph_and_preserve_key_types(engine):
    assert engine.execute('''
        payload = {[false] = "bool", [1] = 42}
        payload.self = payload
        local captured = payload
        function worker()
            return captured == payload, payload.self == payload, payload[false], payload[1]
        end
        local task = thread.spawn("worker")
        assert(task:join(2))
        return task:result()
    ''') == (True, True, 'bool', 42)


def test_global_table_snapshot_precedes_parent_changes(engine):
    assert engine.execute('''
        payload = {answer = 42}
        function worker()
            while not shared.get_key("ready") do sleep(0.005) end
            return payload
        end
        local task = thread.spawn("worker")
        payload.answer = 7
        shared.set_key("ready", true)
        assert(task:join(2))
        return task:result().answer, payload.answer
    ''') == (42, 7)


def test_standard_library_tables_are_rebuilt_instead_of_copied(engine):
    assert engine.execute('''
        payload = {2.9, "ok"}
        function worker()
            return math.floor(payload[1]), string.upper(payload[2]), table.concat({"a", "b"})
        end
        local task = thread.spawn("worker")
        assert(task:join(2))
        return task:result()
    ''') == (2, 'OK', 'ab')


@pytest.mark.parametrize('value', ['function() end', 'coroutine.create(function() end)', 'setmetatable({}, {})'])
def test_unsupported_results_fail_explicitly(engine, value):
    result = engine.execute(f'''
        function worker() return {value} end
        local task = thread.spawn("worker")
        assert(task:join(2))
        return task:error()
    ''')
    assert 'Cannot copy' in result


def test_shutdown_retains_unfinished_native_work_and_rejects_new_tasks(engine):
    entered, release = Event(), Event()
    engine.register_namespace('probe', lambda lua: {'block': lambda: (entered.set(), release.wait(3))})
    try:
        engine.execute('function worker() probe.block() end; thread.spawn("worker")')
        assert entered.wait(1)
        assert engine.shutdown_threads(timeout=0.01) is False
        assert len(engine.thread_manager.list()) == 1
        with pytest.raises(RuntimeError, match='shut'):
            engine.execute('thread.spawn("worker")')
    finally:
        release.set()
    assert engine.shutdown_threads(timeout=1) is True
    assert engine.thread_manager.list() == []


def test_active_thread_limit_recovers_after_completion(engine):
    engine.thread_manager._max_tasks = 1
    entered, release = Event(), Event()
    engine.register_namespace('probe', lambda lua: {'block': lambda: (entered.set(), release.wait(3))})
    try:
        task = engine.execute('function worker() probe.block() end; return thread.spawn("worker")')
        assert entered.wait(1)
        with pytest.raises(RuntimeError, match='limit'):
            engine.execute('thread.spawn("worker")')
    finally:
        release.set()
    assert task.join(1)
    assert engine.execute('function quick() return 42 end; local t = thread.spawn("quick"); assert(t:join(1)); return t:result()') == 42


def test_finished_child_releases_namespace_objects_without_retaining_its_lua_state(engine):
    class Token:
        pass

    tokens = []

    def build(lua):
        token = Token()
        tokens.append(weakref.ref(token))
        return {'token': token}

    engine.register_namespace('probe', build)
    task = engine.execute('function worker() return 42 end; return thread.spawn("worker")')
    assert task.join(2)
    assert task.result() == 42
    gc.collect()
    assert len(tokens) == 2
    assert tokens[0]() is not None
    assert tokens[1]() is None


def test_cancellation_before_target_setup_still_releases_child_runtime(engine, monkeypatch):
    class Token:
        pass

    tokens = []

    def build_namespace(lua):
        token = Token()
        tokens.append(weakref.ref(token))
        return {'token': token}

    build_runtime = engine._build_subruntime_from_snapshot

    def cancel_before_setup(snapshot):
        runtime = build_runtime(snapshot)
        hook = runtime.eval('function() check_stop() end')
        runtime.globals()['debug']['sethook'](hook, '', 1)
        engine.thread_manager.current_cancel_event.set()
        return runtime

    engine.register_namespace('probe', build_namespace)
    monkeypatch.setattr(engine, '_build_subruntime_from_snapshot', cancel_before_setup)
    task = engine.execute('function worker() return 42 end; return thread.spawn("worker")')
    assert task.join(2)
    assert task.is_cancelled()
    assert task.result() is None
    gc.collect()
    assert len(tokens) == 2
    assert tokens[1]() is None
