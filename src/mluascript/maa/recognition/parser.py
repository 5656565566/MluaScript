from __future__ import annotations

from typing import Any

from .models import RecognitionResult


def parse_box(box: Any) -> list[int | float | str]:
    raw_box = list(box)
    parsed_box: list[int | float | str] = []
    for item in raw_box:
        if isinstance(item, (int, float)):
            parsed_box.append(item)
            continue
        text = str(item).strip().strip('"').strip("'")
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1].strip()
        try:
            parsed_box.append(int(text))
            continue
        except ValueError:
            pass
        try:
            parsed_box.append(float(text))
            continue
        except ValueError:
            pass
        parsed_box.append(text)
    return parsed_box


def parse_best_result(best_result: Any) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    score = getattr(best_result, "score", None)
    if score is not None:
        parsed["score"] = score
    text = getattr(best_result, "text", None)
    if text is not None:
        parsed["text"] = text
    box = getattr(best_result, "box", None)
    if box:
        parsed["box"] = parse_box(box)
    return parsed


def parse_recognition_detail(tasker: Any, entry: str, detail: Any, all_results: bool = False) -> RecognitionResult:
    result = RecognitionResult(hit=False, entry=entry)
    if not detail or not getattr(detail, "node_id_list", None):
        return result

    for node_id in detail.node_id_list:
        node = tasker.get_node_detail(node_id)
        if not (node and getattr(node, "recognition", None)):
            continue
        reco = node.recognition
        result.hit = bool(getattr(reco, "hit", False))
        result.name = getattr(reco, "name", None)
        if getattr(reco, "box", None):
            result.box = parse_box(reco.box)
        if getattr(reco, "best_result", None):
            best = parse_best_result(reco.best_result)
            result.score = best.get("score")
            result.text = best.get("text")
            if result.box is None:
                result.box = best.get("box")
        if all_results:
            collected: list[dict[str, Any]] = []
            for attr_name in ("all_results", "results"):
                raw_results = getattr(reco, attr_name, None)
                if raw_results:
                    for item in raw_results:
                        parsed_item = parse_best_result(item)
                        if parsed_item:
                            collected.append(parsed_item)
                    if collected:
                        break
            if not collected and getattr(reco, "best_result", None):
                best_item = parse_best_result(reco.best_result)
                if best_item:
                    collected.append(best_item)
            result.results = collected
        break

    return result
