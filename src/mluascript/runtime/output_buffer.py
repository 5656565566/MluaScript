from __future__ import annotations

from threading import RLock


class TaskOutputBuffer(list[str]):
    """带最大行数限制的任务输出缓冲区"""

    def __init__(self, max_lines: int = 300) -> None:
        super().__init__()
        self._max_lines = 1
        self._version = 0
        self._total_lines = 0
        self._line_open = False
        self._lock = RLock()
        self.set_max_lines(max_lines)

    @property
    def max_lines(self) -> int:
        return self._max_lines

    @property
    def version(self) -> int:
        return self._version

    @property
    def total_lines(self) -> int:
        return self._total_lines

    def append(self, item: object) -> None:
        with self._lock:
            self._append_line(str(item))
            self._trim_to_limit()
            self._version += 1

    def write(self, data: str) -> None:
        """立即展示输出片段，只有显式换行才结束当前行。"""
        if not data:
            return
        parts = data.split('\n')
        with self._lock:
            for index, part in enumerate(parts):
                if index == len(parts) - 1 and not part:
                    break
                self._append_line(part)
                self._line_open = index == len(parts) - 1
            self._trim_to_limit()
            self._version += 1

    def _append_line(self, text: str) -> None:
        if self._line_open and self:
            super().__setitem__(-1, self[-1] + text)
        else:
            super().append(text)
            self._total_lines += 1
        self._line_open = False

    def extend(self, items) -> None:  # type: ignore[override]
        with self._lock:
            changed = False
            for item in items:
                self._append_line(str(item))
                changed = True
            if changed:
                self._trim_to_limit()
                self._version += 1

    def clear(self) -> None:
        with self._lock:
            self._line_open = False
            if not self:
                return
            super().clear()
            self._version += 1

    def set_max_lines(self, max_lines: int) -> int:
        normalized = int(max_lines)
        if normalized <= 0:
            raise ValueError("task output max lines must be a positive integer")
        with self._lock:
            self._max_lines = normalized
            self._trim_to_limit()
            self._version += 1
        return self._max_lines

    def _trim_to_limit(self) -> None:
        overflow = len(self) - self._max_lines
        if overflow > 0:
            del self[:overflow]
