from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import numpy as np

from maa.pipeline import JRecognitionType, JOCR

from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.recognition import (
    RecognitionResult,
    find_color,
    find_feature,
    find_ocr,
    find_ocr_all,
    find_template,
    parse_best_result,
    parse_box,
    parse_recognition_detail,
    run_recognition_direct,
)
from mluascript.maa.types import MaaContextState, MaaPaths


class FakeTaskJob:
    def __init__(self, detail: Any) -> None:
        self.succeeded = True
        self._detail = detail
        self.wait_called = False
        self.job_id = 123

    def wait(self) -> "FakeTaskJob":
        self.wait_called = True
        return self

    def get(self) -> Any:
        return self._detail


class FakeTasker:
    def __init__(self, detail: Any) -> None:
        self.detail = detail
        self.post_task_calls: list[tuple[str, dict[str, Any]]] = []
        self.post_recognition_calls: list[tuple[JRecognitionType, Any, Any]] = []

    def post_task(self, entry: str, override: dict[str, Any]) -> FakeTaskJob:
        self.post_task_calls.append((entry, override))
        return FakeTaskJob(self.detail)

    def post_recognition(self, reco_type: JRecognitionType, param: Any, image: Any) -> FakeTaskJob:
        self.post_recognition_calls.append((reco_type, param, image))
        return FakeTaskJob(self.detail)

    def get_node_detail(self, node_id: str) -> Any:
        return self.detail.node_map[node_id]

    def get_recognition_detail(self, reco_id: int) -> Any:
        return self.detail.recognition_detail


class FakeController:
    def post_screencap(self) -> FakeTaskJob:
        return FakeTaskJob(np.zeros((100, 100, 3), dtype=np.uint8))


def build_detail() -> Any:
    best = SimpleNamespace(score=0.95, text="hello", box=[1, 2, 3, 4])
    reco = SimpleNamespace(
        hit=True,
        name="OCR",
        box=[10, 20, 30, 40],
        best_result=best,
        all_results=[best],
        results=[best],
    )
    node = SimpleNamespace(recognition=reco)
    return SimpleNamespace(node_id_list=["n1"], node_map={"n1": node}, recognition_detail=reco)


def build_context(detail: Any | None = None) -> MaaContext:
    ctx = MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
        tasker=FakeTasker(detail) if detail is not None else None,
    )
    ctx.controller = FakeController()
    return ctx


def test_parse_box_normalizes_values() -> None:
    assert parse_box([1, "2", "3.5", "x"]) == [1, 2, 3.5, "x"]


def test_parse_best_result_extracts_fields() -> None:
    best = SimpleNamespace(score=0.5, text="ok", box=[1, 2, 3, 4])

    parsed = parse_best_result(best)

    assert parsed == {"score": 0.5, "text": "ok", "box": [1, 2, 3, 4]}


def test_parse_recognition_detail_extracts_main_result() -> None:
    tasker = FakeTasker(build_detail())
    detail = build_detail()

    parsed = parse_recognition_detail(tasker, "entry1", detail, all_results=True)

    assert parsed.hit is True
    assert parsed.entry == "entry1"
    assert parsed.name == "OCR"
    assert parsed.box == [10, 20, 30, 40]
    assert parsed.score == 0.95
    assert parsed.text == "hello"
    assert parsed.results == [{"score": 0.95, "text": "hello", "box": [1, 2, 3, 4]}]


def test_run_recognition_direct_returns_none_without_tasker() -> None:
    context = build_context(None)

    assert run_recognition_direct(context, "entry", JRecognitionType.OCR, JOCR()) is None


def test_run_recognition_direct_parses_result_with_tasker() -> None:
    context = build_context(build_detail())

    result = run_recognition_direct(context, "entry", JRecognitionType.OCR, JOCR(), all_results=True)

    assert result is not None
    assert result.hit is True
    assert result.entry == "entry"
    tasker = cast(FakeTasker, context.tasker)
    assert len(tasker.post_recognition_calls) == 1
    assert tasker.post_recognition_calls[0][0] == JRecognitionType.OCR


def test_find_template_wraps_service_result() -> None:
    context = build_context(build_detail())

    result = find_template(context, "entry", template="tpl.png")

    assert result is not None
    assert result["hit"] is True
    assert result["entry"] == "entry"


def test_find_ocr_and_find_ocr_all_wrap_service_result() -> None:
    context = build_context(build_detail())

    single = find_ocr(context, "entry", expected="hello")
    multiple = find_ocr_all(context, "entry", expected="hello")

    assert single is not None
    assert single["text"] == "hello"
    assert multiple is not None
    assert multiple["results"] == [{"score": 0.95, "text": "hello", "box": [1, 2, 3, 4]}]


def test_find_color_and_find_feature_wrap_service_result() -> None:
    context = build_context(build_detail())

    color = find_color(context, "entry")
    feature = find_feature(context, "entry")

    assert color is not None
    assert color["hit"] is True
    assert feature is not None
    assert feature["hit"] is True


def test_recognition_result_to_dict_respects_include_results() -> None:
    result = RecognitionResult(hit=True, entry="entry", results=[{"ok": True}])

    assert result.to_dict() == {"hit": True, "entry": "entry"}
    assert result.to_dict(include_results=True) == {"hit": True, "entry": "entry", "results": [{"ok": True}]}
