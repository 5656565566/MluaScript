from __future__ import annotations

import subprocess

from dataclasses import dataclass
from typing import Any

from lupa.lua54 import LuaRuntime

from .controllers.app import start_app, stop_app
from .controllers.gesture import scroll, swipe, touch_down, touch_move, touch_up
from .controllers.input import click, input_text, key_down, key_up, press_key
from .controllers.query import get_connection_label, get_resolution, get_uuid
from .controllers.screen import screencap
from .controllers.shell import shell
from .lifecycle.runtime import MaaContext
from .recognition.color import find_color
from .recognition.feature import find_feature
from .recognition.ocr import find_ocr, find_ocr_all
from .recognition.template import find_template
from .recognition.nnd import find_nnd
from .types import MaaContextState
from ..runtime.image_bridge import RuntimeImageHandle, build_runtime_image_handle
from ..runtime.utils.table_lua import python_2_lua


def _normalize_roi(roi: Any) -> list[int] | None:
    if roi is None:
        return None
    if isinstance(roi, (list, tuple)):
        return [int(item) for item in roi]
    if hasattr(roi, "keys") and hasattr(roi, "__getitem__"):
        try:
            keys = sorted(key for key in roi.keys() if isinstance(key, int))
            return [int(roi[key]) for key in keys]
        except Exception:
            return None
    return None


def _normalize_string_list(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return items
    if hasattr(value, "keys") and hasattr(value, "__getitem__"):
        try:
            keys = sorted(key for key in value.keys() if isinstance(key, int))
            items = [str(value[key]).strip() for key in keys if str(value[key]).strip()]
            if not items:
                return None
            if len(items) == 1:
                return items[0]
            return items
        except Exception:
            return None
    text = str(value).strip()
    return text or None


def _box_to_rect(box: Any) -> dict[str, Any]:
    if not isinstance(box, list) or len(box) < 4:
        return {"x": None, "y": None, "w": None, "h": None}
    try:
        x = int(box[0])
        y = int(box[1])
        w = int(box[2])
        h = int(box[3])
        return {"x": x, "y": y, "w": w, "h": h}
    except Exception:
        return {"x": None, "y": None, "w": None, "h": None}


def _normalize_recognition_item(kind: str, entry: str, raw: dict[str, Any]) -> dict[str, Any]:
    box = raw.get("box") if isinstance(raw, dict) else None
    rect = _box_to_rect(box)
    return {
        "name": raw.get("name") if isinstance(raw, dict) else None,
        "text": raw.get("text") if isinstance(raw, dict) else None,
        "score": raw.get("score") if isinstance(raw, dict) else None,
        "box": box,
        "x": rect["x"],
        "y": rect["y"],
        "w": rect["w"],
        "h": rect["h"],
    }


def _build_recognition_payload(kind: str, entry: str, raw: dict[str, Any] | None, *, all_results: bool = False) -> dict[str, Any]:
    if not raw:
        return {
            "kind": kind,
            "entry": entry,
            "hit": False,
            "count": 0,
            "items": [],
            "best": None,
            "error": "recognition returned nil",
        }

    hit = bool(raw.get("hit"))
    items: list[dict[str, Any]] = []
    if hit and all_results:
        raw_results = raw.get("results")
        if isinstance(raw_results, list):
            items = [_normalize_recognition_item(kind, entry, item) for item in raw_results if isinstance(item, dict)]
    elif hit:
        items = [_normalize_recognition_item(kind, entry, raw)]

    return {
        "kind": kind,
        "entry": entry,
        "hit": hit,
        "count": len(items),
        "items": items,
        "best": items[0] if items else None,
        "error": None,
    }


@dataclass(slots=True)
class LuaMaaExports:
    lua_runtime: LuaRuntime
    context: MaaContext

    def click(self, x: int, y: int) -> bool:
        return click(self.context, x, y)

    def press_key(self, key: int) -> bool:
        return press_key(self.context, key)

    def key_down(self, key: int) -> bool:
        return key_down(self.context, key)

    def key_up(self, key: int) -> bool:
        return key_up(self.context, key)

    def input_text(self, text: str) -> bool:
        return input_text(self.context, text)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        return swipe(self.context, x1, y1, x2, y2, duration)

    def touch_down(self, x: int, y: int, contact: int = 0) -> bool:
        return touch_down(self.context, x, y, contact)

    def touch_move(self, x: int, y: int, contact: int = 0) -> bool:
        return touch_move(self.context, x, y, contact)

    def touch_up(self, contact: int = 0) -> bool:
        return touch_up(self.context, contact)

    def scroll(self, dx: int, dy: int) -> bool:
        return scroll(self.context, dx, dy)

    def start_app(self, intent: str) -> bool:
        return start_app(self.context, intent)

    def stop_app(self, intent: str) -> bool:
        return stop_app(self.context, intent)

    def shell(self, command: str) -> str | None:
        return shell(self.context, command)

    def get_resolution(self) -> Any:
        width, height = get_resolution(self.context)
        return python_2_lua(self.lua_runtime, {"width": width, "height": height})

    def get_uuid(self) -> str:
        return get_uuid(self.context)

    def get_connection_label(self) -> str:
        return get_connection_label(self.context)

    def is_app_alive(self, intent: str) -> bool:
        label = self.get_connection_label()
        if label.startswith("ADB:"):
            res = self.shell(f"pidof {intent}")
            if res and res.strip():
                return True
            return False
        elif label.startswith("DESKTOP:windows:"):
            res = self.shell(f'tasklist /FI "IMAGENAME eq {intent}" /NH')
            if res and intent.lower() in res.lower():
                return True
            
            try:
                out = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {intent}" /NH', shell=True, text=True)
                if intent.lower() in out.lower():
                    return True
            except Exception:
                pass
            return False
        return False

    def screencap(self) -> RuntimeImageHandle | None:
        image = screencap(self.context)
        if image is None:
            return None
        return build_runtime_image_handle(image)

    def find_template(self, entry: str, template: Any = None, roi: Any = None, threshold: float | None = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        result = find_template(
            self.context,
            entry,
            template=_normalize_string_list(template),
            roi=_normalize_roi(roi),
            threshold=threshold,
            image=img_array,
        )
        return python_2_lua(self.lua_runtime, _build_recognition_payload("template", entry, result))

    def find_ocr(self, entry: str, expected: Any = None, roi: Any = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        result = find_ocr(
            self.context,
            entry,
            expected=_normalize_string_list(expected),
            roi=_normalize_roi(roi),
            image=img_array,
        )
        return python_2_lua(self.lua_runtime, _build_recognition_payload("ocr", entry, result))

    def find_all_ocr(self, entry: str, expected: Any = None, roi: Any = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        result = find_ocr_all(
            self.context,
            entry,
            expected=_normalize_string_list(expected),
            roi=_normalize_roi(roi),
            image=img_array,
        )
        return python_2_lua(self.lua_runtime, _build_recognition_payload("ocr", entry, result, all_results=True))

    def find_color(self, entry: str, lower: Any = None, upper: Any = None, roi: Any = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        
        def _parse_color(val: Any) -> list[list[int]]:
            if not val:
                return []
            if isinstance(val, str):
                val = val.strip().lstrip('#')
                if len(val) == 6:
                    return [[int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16)]]
                return []
            if isinstance(val, (list, tuple)):
                if len(val) > 0 and isinstance(val[0], (int, float)):
                    return [[int(x) for x in val]]
                return [[int(x) for x in row] for row in val]
            return []

        result = find_color(self.context, entry, lower=_parse_color(lower), upper=_parse_color(upper), roi=_normalize_roi(roi), image=img_array)
        return python_2_lua(self.lua_runtime, _build_recognition_payload("color", entry, result))

    def find_feature(self, entry: str, template: Any = None, roi: Any = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        result = find_feature(self.context, entry, template=_normalize_string_list(template), roi=_normalize_roi(roi), image=img_array)
        return python_2_lua(self.lua_runtime, _build_recognition_payload("feature", entry, result))

    def find_nnd(self, entry: str, model: str, targets: Any = None, roi: Any = None, image: RuntimeImageHandle | None = None) -> Any:
        image = image if image else self.screencap()
        img_array = image.get_bgr_array() if image else None
        result = find_nnd(self.context, entry, model, targets=_normalize_string_list(targets), roi=_normalize_roi(roi), image=img_array)
        return python_2_lua(self.lua_runtime, _build_recognition_payload("nnd", entry, result, all_results=True))

    def is_connected(self) -> bool:
        state: MaaContextState = self.context.state
        return bool(state.connected and self.context.controller is not None)


def build_maa_exports(lua_runtime: LuaRuntime, context: MaaContext) -> LuaMaaExports:
    return LuaMaaExports(lua_runtime=lua_runtime, context=context)

