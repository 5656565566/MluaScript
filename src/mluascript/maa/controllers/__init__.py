from __future__ import annotations

from .app import start_app, stop_app
from .base import ensure_controller
from .gesture import scroll, swipe, touch_down, touch_move, touch_up
from .input import click, input_text, key_down, key_up, press_key
from .query import get_connection_label, get_resolution, get_uuid
from .screen import screencap
from .shell import shell

__all__ = [
    "click",
    "ensure_controller",
    "get_connection_label",
    "get_resolution",
    "get_uuid",
    "input_text",
    "key_down",
    "key_up",
    "press_key",
    "screencap",
    "scroll",
    "shell",
    "start_app",
    "stop_app",
    "swipe",
    "touch_down",
    "touch_move",
    "touch_up",
]
