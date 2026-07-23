from __future__ import annotations

from collections.abc import Iterable


class TaskLogBuffer(list[dict[str, str]]):
    """只保留最近若干条记录的任务日志缓冲区"""

    def __init__(self, max_entries: int = 200) -> None:
        super().__init__()
        normalized = int(max_entries)
        if normalized <= 0:
            raise ValueError("task log max entries must be a positive integer")
        self._max_entries = normalized

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def append(self, item: dict[str, str]) -> None:
        super().append(item)
        self._trim_to_limit()

    def extend(self, items: Iterable[dict[str, str]]) -> None:
        super().extend(items)
        self._trim_to_limit()

    def _trim_to_limit(self) -> None:
        overflow = len(self) - self._max_entries
        if overflow > 0:
            del self[:overflow]
