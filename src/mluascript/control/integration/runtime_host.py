from __future__ import annotations

from mluascript.runtime.host_api import HostAPI
from mluascript.runtime.output_buffer import TaskOutputBuffer

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

    def clear_output(self) -> None:
        self.context.print_buffer.clear()

    def set_output_limit(self, max_lines: int) -> int:
        return self.context.print_buffer.set_max_lines(max_lines)

    def get_output_limit(self) -> int:
        buffer = self.context.print_buffer
        if isinstance(buffer, TaskOutputBuffer):
            return buffer.max_lines
        return 300
