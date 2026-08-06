from __future__ import annotations

import inspect

import mluascript.__main__ as entrypoint


def test_program_entrypoint_does_not_own_web_lifecycle() -> None:
    source = inspect.getsource(entrypoint)

    assert "stop_mluascript_web_server" not in source
    assert "mluascript.frontends.web" not in source
