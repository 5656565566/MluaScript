"""MluaScript 首页"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Button, Collapsible, Markdown

from mluascript.shared.consts import (
    WHAT_IS_ROSE,
    WELCOME_MD,
    ABOUT_MD,
    EXAMPLE_MD
)


class Content(VerticalScroll):
    """不可聚焦的垂直滚动容器"""


class HomeScreen(Container):
    DEFAULT_CSS = """
    HomeScreen {
        Content {
            align-horizontal: center;
            margin: 0 1;
            overflow-y: auto;
            height: 1fr;
            scrollbar-gutter: stable;
            & > * {
                max-width: 100;
            }
            MarkdownFence {
                height: auto;
                max-height: initial;
            }
            Collapsible {
                padding-right: 0;
                &.-collapsed {
                    padding-bottom: 1;
                }
            }
            Markdown {
                margin-right: 1;
                padding-right: 1;
                background: transparent;
            }
        }
    }

    #example-btn {
        margin: 1 0; 
        width: 100%;
    }
    """

    def get_code(self, source_file: str | Path) -> str | None:
        pass
    
    def compose(self) -> ComposeResult:
        with Content(can_focus=False):
            yield Markdown(WHAT_IS_ROSE)
            with Collapsible(title="欢迎使用", collapsed=False):
                yield Markdown(WELCOME_MD)
            with Collapsible(title="使用说明"):
                yield Markdown(ABOUT_MD)
            with Collapsible(title="Lua 说明"):
                yield Markdown(EXAMPLE_MD)

            yield Button("展示代码", id="example-btn", variant="primary")

    @on(Button.Pressed, "#example-btn")
    def handle_my_button_click(self, _: Button.Pressed) -> None:
        self.notify("功能已留空", title="展示代码", severity="warning")
