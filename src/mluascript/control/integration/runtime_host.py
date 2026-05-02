from __future__ import annotations

from mluascript.runtime.host_api import HostAPI

from .models import ScriptRunContext


class RuntimeHost(HostAPI):
    """把 integration run context 包装为 runtime 可消费宿主"""

    def __init__(self, context: ScriptRunContext) -> None:
        self.context = context

    def print(self, message: str) -> None:
        text = str(message)
        self.context.print_buffer.append(text)

    def log(self, level: str, message: str) -> None:
        text = str(message)
        level_name = str(level or "INFO").upper()
        self.context.log_buffer.append(
            {
                "level": level_name,
                "message": text,
            }
        )

    def notify(self, message: str) -> None:
        _ = message

    def check_stop(self) -> None:
        self.context.stopper.check()
