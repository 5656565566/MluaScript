from __future__ import annotations


class TaskOutputBuffer(list[str]):
    """带最大行数限制的任务输出缓冲区"""

    def __init__(self, max_lines: int = 300) -> None:
        super().__init__()
        self._max_lines = 1
        self._version = 0
        self._total_lines = 0
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
        super().append(str(item))
        self._total_lines += 1
        self._trim_to_limit()
        self._version += 1

    def extend(self, items) -> None:  # type: ignore[override]
        changed = False
        for item in items:
            super().append(str(item))
            self._total_lines += 1
            changed = True
        if changed:
            self._trim_to_limit()
            self._version += 1

    def clear(self) -> None:
        if not self:
            return
        super().clear()
        self._version += 1

    def set_max_lines(self, max_lines: int) -> int:
        normalized = int(max_lines)
        if normalized <= 0:
            raise ValueError("task output max lines must be a positive integer")
        self._max_lines = normalized
        self._trim_to_limit()
        self._version += 1
        return self._max_lines

    def _trim_to_limit(self) -> None:
        overflow = len(self) - self._max_lines
        if overflow > 0:
            del self[:overflow]
