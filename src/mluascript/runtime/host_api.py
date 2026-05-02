from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HostAPI(Protocol):
    """
    宿主向 Lua 运行时提供的能力接口
    注入给 LuaEngine 使用
    """

    def print(self, message: str) -> None:
        """一个 lua 输出源"""
        ...

    def log(self, level: str, message: str) -> None:
        """处理来自 Lua 的分级日志"""
        ...

    def notify(self, message: str) -> None:
        """处理通知"""
        ...

    def check_stop(self) -> None:
        """检查停止信号 若需要终止执行 应抛出运行时退出异常"""
        ...
