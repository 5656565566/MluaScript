from __future__ import annotations

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Static

class CodeScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    CodeScreen {
        #code {
            border: heavy $accent;
            margin: 2 4;
            scrollbar-gutter: stable;
            Static {
                width: auto;
            }
        }
    }
    """

    BINDINGS = [("escape", "dismiss", "Dismiss code")]

    def __init__(self, title: str, code: str) -> None:
        super().__init__()
        self.code = code
        self.title = title

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="code"):
            yield Static(
                Syntax(self.code, lexer="lua", indent_guides=True, line_numbers=True),
                expand=True,
            )

    def on_mount(self) -> None:
        code_widget = self.query_one("#code")
        code_widget.border_title = self.title
        code_widget.border_subtitle = "按 [b]escape (Esc)[/b] 退出"