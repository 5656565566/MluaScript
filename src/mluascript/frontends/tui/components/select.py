"""本地化 Select 组件"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Generic, Hashable, TypeVar, cast

from rich.console import RenderableType
from textual.binding import Binding
from textual.widgets import Select
from textual.widgets._select import SelectCurrent, SelectOverlay

SelectType = TypeVar("SelectType", bound=Hashable)


class ChineseSelectOverlay(SelectOverlay):
    """中文化的 Select 下拉层"""

    BINDINGS = [Binding("escape", "dismiss", "关闭菜单")]


class _Select(Select[SelectType], Generic[SelectType]):

    BINDINGS = [
        Binding("enter,down,space,up", "show_overlay", "显示菜单", show=False),
    ]

    def __init__(
        self,
        options: Iterable[tuple[RenderableType, SelectType]],
        *,
        prompt: str = "请选择",
        allow_blank: bool = True,
        value: Any = Select.NULL,
        type_to_search: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
        compact: bool = False,
    ) -> None:
        super().__init__(
            options,
            prompt=prompt,
            allow_blank=allow_blank,
            value=cast(Any, value),
            type_to_search=type_to_search,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            tooltip=tooltip,
            compact=compact,
        )

    def compose(self):
        yield SelectCurrent(self.prompt)
        yield ChineseSelectOverlay(self._type_to_search)