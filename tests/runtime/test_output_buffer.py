from concurrent.futures import ThreadPoolExecutor

from mluascript.runtime.output_buffer import TaskOutputBuffer


def test_partial_writes_update_the_existing_line_and_version():
    output = TaskOutputBuffer()
    output.write('a')
    version = output.version
    output.write('b')
    assert output == ['ab']
    assert output.version > version
    assert output.total_lines == 1
    output.append('c')
    output.write('d')
    assert output == ['abc', 'd']
    assert output.total_lines == 2


def test_empty_lines_and_trailing_newline_do_not_create_a_phantom_line():
    output = TaskOutputBuffer()
    output.write('\n\none\n')
    assert output == ['', '', 'one']
    output.write('two')
    output.write('\n')
    output.append('')
    assert output == ['', '', 'one', 'two', '']
    assert output.total_lines == 5


def test_extend_finishes_a_partial_line_without_changing_normal_append_behavior():
    output = TaskOutputBuffer()
    output.append('normal')
    output.write('partial')
    output.extend(['-end', 'next'])
    assert output == ['normal', 'partial-end', 'next']
    assert output.total_lines == 3


def test_clear_resets_partial_line_state_and_preserves_lifetime_count():
    output = TaskOutputBuffer()
    output.write('old')
    output.clear()
    output.write('new')
    assert output == ['new']
    assert output.total_lines == 2


def test_multiline_writes_obey_the_existing_line_limit():
    output = TaskOutputBuffer(max_lines=2)
    output.write('a\nb\nc')
    output.write('-end')
    assert output == ['b', 'c-end']
    assert output.total_lines == 3


def test_concurrent_writes_keep_each_multiline_call_together():
    output = TaskOutputBuffer(max_lines=400)

    def write(index):
        output.write(f'{index}-a\n{index}-b\n')

    with ThreadPoolExecutor(max_workers=8) as writers:
        list(writers.map(write, range(100)))
    assert len(output) == output.total_lines == 200
    for index in range(0, len(output), 2):
        assert output[index].removesuffix('-a') == output[index + 1].removesuffix('-b')
