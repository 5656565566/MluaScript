from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from lupa.lua54 import LuaRuntime
from PIL import Image

from mluascript.maa.lua_exports import build_maa_exports
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths
from mluascript.runtime.image_bridge import RuntimeImageHandle, build_runtime_image_handle
from mluascript.runtime.utils.table_lua import lua_2_python


class FakeWaitable:
    def __init__(self) -> None:
        self.wait_called = False

    def wait(self) -> "FakeWaitable":
        self.wait_called = True
        return self


class FakeResultJob(FakeWaitable):
    def __init__(self, succeeded: bool, result: Any) -> None:
        super().__init__()
        self.succeeded = succeeded
        self._result = result

    def get(self) -> Any:
        return self._result


@dataclass
class FakeImage:
    shape: tuple[int, int, int]

    def __array__(self, dtype=None):
        array = np.zeros(self.shape, dtype=np.uint8)
        array[:, :, 0] = 10
        array[:, :, 1] = 20
        array[:, :, 2] = 30
        return array


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.last_job: FakeWaitable | FakeResultJob | None = None
        self.resolution = (1280, 720)
        self.uuid = "fake-controller"

    def _record(self, name: str, *args: Any, result: FakeWaitable | FakeResultJob | None = None) -> FakeWaitable | FakeResultJob:
        self.calls.append((name, args))
        self.last_job = result or FakeWaitable()
        return self.last_job

    def post_click(self, x: int, y: int) -> FakeWaitable:
        return self._record("post_click", x, y)

    def post_click_key(self, key: int) -> FakeWaitable:
        return self._record("post_click_key", key)

    def post_key_down(self, key: int) -> FakeWaitable:
        return self._record("post_key_down", key)

    def post_key_up(self, key: int) -> FakeWaitable:
        return self._record("post_key_up", key)

    def post_input_text(self, text: str) -> FakeWaitable:
        return self._record("post_input_text", text)

    def post_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> FakeWaitable:
        return self._record("post_swipe", x1, y1, x2, y2, duration)

    def post_touch_down(self, x: int, y: int, contact: int) -> FakeWaitable:
        return self._record("post_touch_down", x, y, contact)

    def post_touch_move(self, x: int, y: int, contact: int) -> FakeWaitable:
        return self._record("post_touch_move", x, y, contact)

    def post_touch_up(self, contact: int) -> FakeWaitable:
        return self._record("post_touch_up", contact)

    def post_scroll(self, dx: int, dy: int) -> FakeWaitable:
        return self._record("post_scroll", dx, dy)

    def post_screencap(self) -> FakeResultJob:
        image = FakeImage(shape=(720, 1280, 3))
        return self._record("post_screencap", result=FakeResultJob(True, image))  # type: ignore[return-value]

    def post_start_app(self, intent: str) -> FakeWaitable:
        return self._record("post_start_app", intent)

    def post_stop_app(self, intent: str) -> FakeWaitable:
        return self._record("post_stop_app", intent)



def build_context(controller: FakeController | None = None, connected: bool = True) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(connected=connected, connection_label="ADB:test" if connected else None),
        controller=controller,
    )



def test_build_maa_exports_exposes_device_actions() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    controller = FakeController()
    exports = build_maa_exports(lua, build_context(controller))

    assert exports.click(10, 20) is True
    assert exports.press_key(13) is True
    assert exports.key_down(14) is True
    assert exports.key_up(15) is True
    assert exports.input_text("hello") is True
    assert exports.swipe(1, 2, 3, 4, 500) is True
    assert exports.touch_down(11, 22, 1) is True
    assert exports.touch_move(33, 44, 1) is True
    assert exports.touch_up(1) is True
    assert exports.scroll(5, 6) is True
    assert exports.start_app("com.demo.app") is True
    assert exports.stop_app("com.demo.app") is True

    assert controller.calls == [
        ("post_click", (10, 20)),
        ("post_click_key", (13,)),
        ("post_key_down", (14,)),
        ("post_key_up", (15,)),
        ("post_input_text", ("hello",)),
        ("post_swipe", (1, 2, 3, 4, 500)),
        ("post_touch_down", (11, 22, 1)),
        ("post_touch_move", (33, 44, 1)),
        ("post_touch_up", (1,)),
        ("post_scroll", (5, 6)),
        ("post_start_app", ("com.demo.app",)),
        ("post_stop_app", ("com.demo.app",)),
    ]



def test_build_maa_exports_exposes_query_values() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    controller = FakeController()
    exports = build_maa_exports(lua, build_context(controller))

    resolution = lua_2_python(exports.get_resolution())

    assert resolution == {"width": 1280, "height": 720}
    assert exports.get_uuid() == "fake-controller"
    assert exports.get_connection_label() == "ADB:test"
    assert exports.is_connected() is True



def test_build_maa_exports_returns_runtime_image_handle_for_screencap() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    controller = FakeController()
    exports = build_maa_exports(lua, build_context(controller))

    image = exports.screencap()

    assert isinstance(image, RuntimeImageHandle)
    assert image.width == 1280
    assert image.height == 720
    assert image.mode == "RGB"
    assert image.channels == 3
    assert isinstance(image.to_pil_image(), Image.Image)
    assert image.to_png_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert controller.calls == [("post_screencap", ())]
    assert controller.last_job is not None
    assert controller.last_job.wait_called is True



def test_runtime_image_handle_supports_crop() -> None:
    handle = build_runtime_image_handle(np.zeros((100, 200, 3), dtype=np.uint8))

    cropped = handle.crop(10, 20, 30, 40)

    assert isinstance(cropped, RuntimeImageHandle)
    assert cropped.width == 30
    assert cropped.height == 40
    assert cropped.mode == "RGB"
    assert cropped.channels == 3



def test_build_maa_exports_reports_not_connected_when_context_is_unbound() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_maa_exports(lua, build_context(controller=None, connected=False))

    assert exports.is_connected() is False



def test_build_maa_exports_returns_result_table_for_find_ocr(mocker) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_maa_exports(lua, build_context(FakeController()))
    mocker.patch("mluascript.maa.lua_exports.find_ocr", return_value={
        "hit": True,
        "entry": "ocr_node",
        "text": "确认",
        "score": 0.98,
        "box": [10, 20, 30, 40],
        "name": "OCR",
    })

    result = lua_2_python(exports.find_ocr("ocr_node", "确认", [10, 20, 30, 40]))

    assert result == {
        "kind": "ocr",
        "entry": "ocr_node",
        "hit": True,
        "count": 1,
        "items": [{
            "name": "OCR",
            "text": "确认",
            "score": 0.98,
            "box": [10, 20, 30, 40],
            "x": 10,
            "y": 20,
            "w": 30,
            "h": 40,
        }],
        "best": {
            "name": "OCR",
            "text": "确认",
            "score": 0.98,
            "box": [10, 20, 30, 40],
            "x": 10,
            "y": 20,
            "w": 30,
            "h": 40,
        },
    }



def test_build_maa_exports_returns_result_table_for_find_all_ocr(mocker) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_maa_exports(lua, build_context(FakeController()))
    mocker.patch("mluascript.maa.lua_exports.find_ocr_all", return_value={
        "hit": True,
        "entry": "ocr_all_node",
        "results": [
            {"text": "确认", "score": 0.9, "box": [1, 2, 3, 4]},
            {"text": "取消", "score": 0.8, "box": [5, 6, 7, 8]},
        ],
    })

    result = lua_2_python(exports.find_all_ocr("ocr_all_node", ["确认", "取消"], [1, 2, 3, 4]))

    assert result == {
        "kind": "ocr",
        "entry": "ocr_all_node",
        "hit": True,
        "count": 2,
        "items": [
            {
                "text": "确认",
                "score": 0.9,
                "box": [1, 2, 3, 4],
                "x": 1,
                "y": 2,
                "w": 3,
                "h": 4,
            },
            {
                "text": "取消",
                "score": 0.8,
                "box": [5, 6, 7, 8],
                "x": 5,
                "y": 6,
                "w": 7,
                "h": 8,
            },
        ],
        "best": {
            "text": "确认",
            "score": 0.9,
            "box": [1, 2, 3, 4],
            "x": 1,
            "y": 2,
            "w": 3,
            "h": 4,
        },
    }



def test_build_maa_exports_returns_empty_result_table_for_unhit_recognition(mocker) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_maa_exports(lua, build_context(FakeController()))
    mocker.patch("mluascript.maa.lua_exports.find_feature", return_value={"hit": False, "entry": "feature_node"})

    result = lua_2_python(exports.find_feature("feature_node"))

    assert result == {
        "kind": "feature",
        "entry": "feature_node",
        "hit": False,
        "count": 0,
        "items": {},
    }



def test_build_maa_exports_normalizes_template_and_color_results(mocker) -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    exports = build_maa_exports(lua, build_context(FakeController()))
    mocker.patch("mluascript.maa.lua_exports.find_template", return_value={
        "hit": True,
        "entry": "template_node",
        "name": "TemplateMatch",
        "score": 0.77,
        "box": [11, 22, 33, 44],
    })
    mocker.patch("mluascript.maa.lua_exports.find_color", return_value={
        "hit": True,
        "entry": "color_node",
        "box": [3, 4, 5, 6],
        "name": "ColorMatch",
    })

    template_result = lua_2_python(exports.find_template("template_node", ["a.png", "b.png"], [11, 22, 33, 44], 0.77))
    color_result = lua_2_python(exports.find_color("color_node", [3, 4, 5, 6]))

    assert template_result == {
        "kind": "template",
        "entry": "template_node",
        "hit": True,
        "count": 1,
        "items": [{
            "name": "TemplateMatch",
            "score": 0.77,
            "box": [11, 22, 33, 44],
            "x": 11,
            "y": 22,
            "w": 33,
            "h": 44,
        }],
        "best": {
            "name": "TemplateMatch",
            "score": 0.77,
            "box": [11, 22, 33, 44],
            "x": 11,
            "y": 22,
            "w": 33,
            "h": 44,
        },
    }
    assert color_result == {
        "kind": "color",
        "entry": "color_node",
        "hit": True,
        "count": 1,
        "items": [{
            "name": "ColorMatch",
            "box": [3, 4, 5, 6],
            "x": 3,
            "y": 4,
            "w": 5,
            "h": 6,
        }],
        "best": {
            "name": "ColorMatch",
            "box": [3, 4, 5, 6],
            "x": 3,
            "y": 4,
            "w": 5,
            "h": 6,
        },
    }
