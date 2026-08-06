"""TUI 列表分页工具。"""

from __future__ import annotations

from typing import Sequence, TypeVar


ItemT = TypeVar("ItemT")


def paginate_items(
    items: Sequence[ItemT],
    page_index: int,
    page_size: int,
) -> tuple[list[ItemT], int, int]:
    """返回当前页、收敛后的页码和总页数。"""

    if not items:
        return [], 0, 0
    total_pages = (len(items) + page_size - 1) // page_size
    current_page = min(max(page_index, 0), total_pages - 1)
    start = current_page * page_size
    return list(items[start : start + page_size]), current_page, total_pages
