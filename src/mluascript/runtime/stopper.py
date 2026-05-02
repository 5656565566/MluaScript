from __future__ import annotations

from threading import Event

from .exception import LuaExitException


class Stopper:
    """运行时停止控制器"""

    def __init__(self) -> None:
        self._stop_event = Event()

    @property
    def is_stop_requested(self) -> bool:
        """当前是否已请求停止"""
        return self._stop_event.is_set()

    def request_stop(self) -> None:
        """请求停止当前运行中的 Lua 执行"""
        self._stop_event.set()

    def check(self) -> None:
        """检查停止标记 如已请求停止则抛出退出异常"""
        if self.is_stop_requested:
            raise LuaExitException("Execution stopped by host")

    def reset(self) -> None:
        """清空停止标记 供下一次执行复用"""
        self._stop_event.clear()
