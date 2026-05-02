from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, Thread
from typing import Any


@dataclass(slots=True)
class WebServerRuntimeState:
    host: str = "127.0.0.1"
    port: int = 18080
    server_url: str = ""
    running: bool = False
    thread: Thread | None = None
    should_stop: bool = False
    server: Any | None = None


_web_runtime_state = WebServerRuntimeState()
_web_runtime_lock = Lock()


def get_web_runtime_state() -> WebServerRuntimeState:
    return _web_runtime_state


def get_web_runtime_lock() -> Lock:
    return _web_runtime_lock
