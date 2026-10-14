from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from maa.controller import CustomController

from mluascript.maa.controllers.shell import shell
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaPaths


def test_native_string_buffer_reads_exact_length_in_subprocess() -> None:
    # Keep an upstream native access violation out of the pytest process.
    result = subprocess.run(
        [sys.executable, "-c", '''
import ctypes
from concurrent.futures import ThreadPoolExecutor
import mluascript.maa
from maa.buffer import StringBuffer
from maa.library import Library

payloads = ["", "abc\\0def", "\\0" + "Q" * 1048576, "Q" * 4194304, "中文\\0输出", "tail\\0"]
def check(payload):
    buffer = StringBuffer()
    assert buffer.set(payload)
    # Simulate API signatures being reassigned by the binding.
    Library.framework().MaaStringBufferGet.restype = ctypes.c_char_p
    assert buffer.get() == payload
    assert StringBuffer().get() == ""

for payload in payloads:
    check(payload)
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(check, ["parallel\\0" + "Q" * 4096] * 32))
buffer = StringBuffer()
assert buffer.set(b"\\xff\\0binary")
try:
    buffer.get()
except UnicodeDecodeError:
    pass
else:
    raise AssertionError("StringBuffer.get must retain strict UTF-8 decoding")
print("exact")
'''],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == "exact"


def test_shell_reads_native_output_with_embedded_nul() -> None:
    class ShellController(CustomController):
        def connect(self) -> bool:
            return True

        def request_uuid(self) -> str:
            return "shell-test"

        def screencap(self):
            return np.zeros((720, 1280, 3), dtype=np.uint8)

        def shell(self, command: str, timeout: int) -> str:
            return "中文\0" + "Q" * 1048576

    controller = ShellController()
    assert controller.post_connection().wait().succeeded
    context = MaaContext(paths=MaaPaths(library_dir=Path('.'), resource_dir=Path('.')), controller=controller)
    assert shell(context, "test-nul-output") == "中文\0" + "Q" * 1048576
