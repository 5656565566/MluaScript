from __future__ import annotations

from mluascript.runtime.utils.virtual_io import VirtualIO


def test_virtual_io_write_read_and_clear() -> None:
    io = VirtualIO()

    assert io.write("hello") is True
    assert io.write(" world") is True
    assert io.read() == ["hello", " world"]

    io.clear()
    assert io.read() == []


def test_virtual_io_calls_update_handler() -> None:
    io = VirtualIO()
    captured: list[str] = []
    io.update_buffer_handler = captured.append

    io.write("chunk")

    assert captured == ["chunk"]


def test_virtual_io_flush_and_close_are_noops() -> None:
    io = VirtualIO()

    assert io.flush() is None
    assert io.close() is None
