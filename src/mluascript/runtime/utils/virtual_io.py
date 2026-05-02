from typing import Callable

class VirtualIO:

    def __init__(self) -> None:
        self.content: list[str] = []
        self.update_buffer_handler: Callable[[str], None] | None = None

    def write(self, data: str) -> bool:
        self.content.append(data)
        if self.update_buffer_handler:
            self.update_buffer_handler(data)
        return True

    def clear(self) -> None:
        self.content.clear()

    def read(self) -> list[str]:
        return self.content

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass