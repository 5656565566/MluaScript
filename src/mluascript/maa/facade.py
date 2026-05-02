from __future__ import annotations

from .connections.session import ConnectionSession, ConnectionSessionStore
from .lifecycle.runtime import MaaContext, create_maa_context


class MaaFacade:
    """Maa 核内部统一入口"""

    def __init__(self, context: MaaContext, sessions: ConnectionSessionStore | None = None) -> None:
        self.context = context
        self.sessions = sessions or ConnectionSessionStore()

    @classmethod
    def create_default(cls) -> "MaaFacade":
        return cls(create_maa_context())

    def attach_session(self, session: ConnectionSession) -> None:
        self.sessions.set_current(session)
        self.context.controller = session.controller
        self.context.mark_connected(session.info.label)

    def get_current_session(self) -> ConnectionSession | None:
        return self.sessions.get_current()

    def clear_session(self) -> None:
        self.sessions.clear()
        self.context.controller = None
        self.context.mark_connected(None)
