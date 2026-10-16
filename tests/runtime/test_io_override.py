from __future__ import annotations

from types import SimpleNamespace

import pytest

from mluascript.control.integration.runtime_host import RuntimeHost
from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.exception import LuaExitException
from mluascript.runtime.output_buffer import TaskOutputBuffer
from mluascript.runtime.stopper import Stopper


@pytest.fixture
def runtime(tmp_path):
    context = SimpleNamespace(print_buffer=TaskOutputBuffer(), log_buffer=[], stopper=Stopper())
    engine = LuaEngine(tmp_path, RuntimeHost(context))
    yield engine, context.print_buffer
    assert engine.shutdown_threads(timeout=2)


def test_io_write_appends_chunks_without_adding_newlines(runtime):
    engine, output = runtime
    assert engine.execute('return io.write("hello", " ", 42)') is True
    version = output.version
    assert output == ['hello 42']
    engine.execute('io.write("!")')
    assert output == ['hello 42!']
    assert output.version > version
    assert output.total_lines == 1


def test_io_write_and_print_share_one_output_stream(runtime):
    engine, output = runtime
    engine.execute('io.write("prefix-"); print("line", 42); io.write("tail"); print("-end"); print("next")')
    assert output == ['prefix-line\t42', 'tail-end', 'next']


@pytest.mark.parametrize('script', [
    'io.write("one\\n\\ntwo\\n")',
    'io.write("one"); io.write("\\n"); io.write("\\n"); io.write("two\\n")',
])
def test_io_write_preserves_explicit_and_split_newlines(runtime, script):
    engine, output = runtime
    engine.execute(script)
    assert output == ['one', '', 'two']
    assert output.total_lines == 3


def test_empty_io_write_does_not_add_an_output_line(runtime):
    engine, output = runtime
    version = output.version
    assert engine.execute('return io.write()') is True
    assert output == [] and output.version == version


def test_clear_and_limit_apply_to_partial_io_output(runtime):
    engine, output = runtime
    engine.execute('''
        io.write("discard")
        clear_output()
        io.write("new\\n2\\n3")
        set_output_limit(2)
        io.write("-tail")
    ''')
    assert output == ['2', '3-tail']
    assert output.max_lines == 2
    assert output.total_lines == 4


def test_redirected_io_write_still_writes_the_file_and_can_restore_default_output(runtime, tmp_path):
    engine, output = runtime
    target = tmp_path / 'redirected.txt'
    lua = engine.inject()
    lua.globals()['target_path'] = target.as_posix()
    engine.execute('''
        local default = io.output()
        local file = assert(io.open(target_path, "wb"))
        io.output(file)
        io.write("file", 42, "\\n")
        io.output(default)
        file:close()
        io.write("screen")
    ''')
    assert target.read_bytes() == b'file42\n'
    assert output == ['screen']


def test_os_exit_stops_the_script_without_discarding_partial_output(runtime):
    engine, output = runtime
    with pytest.raises(LuaExitException, match='expected exit'):
        engine.execute('io.write("before"); os.exit("expected exit"); io.write("after")')
    assert output == ['before']


def test_child_io_write_uses_the_same_output_stream(runtime):
    engine, output = runtime
    engine.execute('''
        io.write("main")
        function worker() io.write("-child") end
        local task = thread.spawn("worker")
        assert(task:join(2))
        assert(task:error() == "", task:error())
        print("-end")
    ''')
    assert output == ['main-child-end']


def test_child_os_exit_uses_the_existing_task_stop_contract(runtime):
    engine, output = runtime
    result = engine.execute('''
        function worker() io.write("child"); os.exit("child exit"); io.write("unreachable") end
        local task = thread.spawn("worker")
        assert(task:join(2))
        print("-main")
        return task:error()
    ''')
    assert 'child exit' in result
    assert output == ['child-main']
