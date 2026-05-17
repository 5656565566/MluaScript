from __future__ import annotations

from threading import Event
from typing import Callable, Iterable, Iterator, TypeVar

T = TypeVar("T")


def unique_by_key(items: Iterable[T], key: Callable[[T], str]) -> list[T]:
    """按字符串键去重 保留最后一次出现的元素顺序"""
    cache: dict[str, T] = {}
    order: list[str] = []
    for item in items:
        item_key = key(item)
        if item_key not in cache:
            order.append(item_key)
        cache[item_key] = item
    return [cache[item_key] for item_key in order]


def iter_until(event: Event, interval: float = 0.0) -> Iterator[None]:
    """在停止事件触发前持续迭代"""
    while not event.is_set():
        yield
        if interval > 0:
            event.wait(interval)
