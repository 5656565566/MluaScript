from __future__ import annotations

import ctypes

from maa.buffer import StringBuffer
from maa.define import MaaBool, MaaControllerHandle, MaaCtrlId, MaaStringBufferHandle
from maa.library import Library


def _get_string_buffer(buffer: StringBuffer) -> str:
    library = Library.framework()
    # 独立 ctypes 函数不受绑定重设签名影响，也不与并发读取共享 restype。
    # c_char_p 会提前按 NUL 截断，必须从原生指针按真实长度读取。
    get_buffer = library["MaaStringBufferGet"]
    get_buffer.argtypes = [MaaStringBufferHandle]
    get_buffer.restype = ctypes.c_void_p
    pointer = get_buffer(buffer._handle)
    size = library.MaaStringBufferSize(buffer._handle)
    if not size:
        return ""
    if not pointer:
        raise RuntimeError("Maa string buffer has a size but no data pointer")
    return ctypes.string_at(pointer, size).decode()


def install_string_buffer_fix() -> None:
    """修正缓冲区读取长度，保留 StringBuffer.get 的 str 和 UTF-8 解码契约"""
    StringBuffer.get = _get_string_buffer


def configure_shell_api() -> None:
    """补齐 maafw 5.14.0 缺失的 shell 绑定签名，保留新版已有声明"""
    library = Library.framework()
    with Library._api_lock:
        post_shell = library.MaaControllerPostShell
        if post_shell.argtypes is None:
            post_shell.restype = MaaCtrlId
            post_shell.argtypes = [MaaControllerHandle, ctypes.c_char_p, ctypes.c_int64]
        get_output = library.MaaControllerGetShellOutput
        if get_output.argtypes is None:
            get_output.restype = MaaBool
            get_output.argtypes = [MaaControllerHandle, MaaStringBufferHandle]
