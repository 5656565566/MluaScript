from __future__ import annotations

from .base import run_controller_operation
from ..lifecycle.runtime import MaaContext


def _active_touch_contacts(context: MaaContext) -> set[int]:
    contacts = context.state.extras.get("active_touch_contacts")
    if not isinstance(contacts, set):
        contacts = set()
        context.state.extras["active_touch_contacts"] = contacts
    return contacts


def swipe(context: MaaContext, x1: int | float, y1: int | float, x2: int | float, y2: int | float, duration: int = 300) -> bool:
    normalized = (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)), int(round(duration)))
    run_controller_operation(
        context,
        lambda controller: controller.post_swipe(*normalized),
        operation="swipe",
        replay_after_reconnect=True,
    )
    return True


def touch_down(context: MaaContext, x: int | float, y: int | float, contact: int = 0) -> bool:
    normalized_contact = int(round(contact))
    run_controller_operation(
        context,
        lambda controller: controller.post_touch_down(int(round(x)), int(round(y)), normalized_contact),
        operation="touch down",
    )
    _active_touch_contacts(context).add(normalized_contact)
    return True


def touch_move(context: MaaContext, x: int | float, y: int | float, contact: int = 0) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_touch_move(int(round(x)), int(round(y)), int(round(contact))),
        operation="touch move",
    )
    return True


def touch_up(context: MaaContext, contact: int = 0) -> bool:
    normalized_contact = int(round(contact))
    run_controller_operation(
        context,
        lambda controller: controller.post_touch_up(normalized_contact),
        operation="touch up",
    )
    _active_touch_contacts(context).discard(normalized_contact)
    return True


def scroll(context: MaaContext, dx: int | float, dy: int | float) -> bool:
    normalized_dx = int(round(dx))
    normalized_dy = int(round(dy))
    run_controller_operation(
        context,
        lambda controller: controller.post_scroll(normalized_dx, normalized_dy),
        operation="scroll",
        replay_after_reconnect=True,
    )
    return True
