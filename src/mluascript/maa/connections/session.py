from __future__ import annotations

from dataclasses import dataclass

from .models import ConnectionInfo


@dataclass(slots=True)
class ConnectionSession:
    """当前 Maa 连接会话"""

    info: ConnectionInfo
    controller: object | None = None


class ConnectionSessionStore:
    """Maa 连接会话存储"""

    def __init__(self) -> None:
        self._current: ConnectionSession | None = None

    def set_current(self, session: ConnectionSession) -> None:
        self._current = session

    def get_current(self) -> ConnectionSession | None:
        return self._current

    def require_current(self) -> ConnectionSession:
        if self._current is None:
            raise RuntimeError("No active Maa connection session")
        return self._current

    def has_current(self) -> bool:
        return self._current is not None

    def clear(self) -> None:
        self._current = None
