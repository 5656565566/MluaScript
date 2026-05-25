from __future__ import annotations

from .base import MaaController, ensure_controller, wait_for
from ..lifecycle.runtime import MaaContext


def _active_touch_contacts(context: MaaContext) -> set[int]:
    contacts = context.state.extras.get("active_touch_contacts")
    if not isinstance(contacts, set):
        contacts = set()
        context.state.extras["active_touch_contacts"] = contacts
    return contacts


def swipe(context: MaaContext, x1: int | float, y1: int | float, x2: int | float, y2: int | float, duration: int = 300) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_swipe(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)), int(round(duration))))
    return True


def touch_down(context: MaaContext, x: int | float, y: int | float, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    normalized_contact = int(round(contact))
    wait_for(controller.post_touch_down(int(round(x)), int(round(y)), normalized_contact))
    _active_touch_contacts(context).add(normalized_contact)
    return True


def touch_move(context: MaaContext, x: int | float, y: int | float, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_touch_move(int(round(x)), int(round(y)), int(round(contact))))
    return True


def touch_up(context: MaaContext, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    normalized_contact = int(round(contact))
    wait_for(controller.post_touch_up(normalized_contact))
    _active_touch_contacts(context).discard(normalized_contact)
    return True


def scroll(context: MaaContext, dx: int | float, dy: int | float) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_scroll(int(round(dx)), int(round(dy))))
    return True
