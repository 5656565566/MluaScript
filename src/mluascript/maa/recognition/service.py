from __future__ import annotations

from typing import Any
import numpy as np

from maa.pipeline import JRecognitionType

from mluascript.shared.logging import logger

from ..lifecycle.runtime import MaaContext
from ..controllers.screen import screencap
from .models import RecognitionResult
from .parser import parse_box, parse_best_result


def run_recognition_direct(
    context: MaaContext,
    entry: str,
    reco_type: JRecognitionType,
    reco_param: Any,
    all_results: bool = False,
    image: Any | None = None,
) -> RecognitionResult | None:
    if context.tasker is None:
        logger.error(f"识别任务执行失败 [{entry}]: tasker 未初始化")
        return None

    try:
        if image is None:
            image = screencap(context)
            if image is None:
                logger.error(f"识别任务执行失败 [{entry}]: 无法获取屏幕截图")
                return None

        if not isinstance(image, np.ndarray):
            image_array = np.array(image)
        else:
            image_array = image

        job = context.tasker.post_recognition(reco_type, reco_param, image_array)
        job.wait()

        detail = None
        task_detail = context.tasker.get_task_detail(job.job_id)
        node_ids = getattr(task_detail, "node_id_list", None) if task_detail is not None else None
        if node_ids:
            node_detail = context.tasker.get_node_detail(node_ids[-1])
            detail = getattr(node_detail, "recognition", None) if node_detail is not None else None

        if detail is None:
            return RecognitionResult(hit=False, entry=entry, results=[] if all_results else [])

        result = RecognitionResult(hit=detail.hit, entry=entry)
        result.name = detail.name
        if getattr(detail, "box", None):
            result.box = parse_box(detail.box)

        if getattr(detail, "best_result", None):
            best = parse_best_result(detail.best_result)
            result.score = best.get("score")
            result.text = best.get("text")
            if result.box is None and "box" in best:
                result.box = best["box"]

        if all_results:
            collected: list[dict[str, Any]] = []
            for attr_name in ("all_results", "filtered_results"):
                raw_results = getattr(detail, attr_name, None)
                if raw_results:
                    for item in raw_results:
                        parsed_item = parse_best_result(item)
                        if parsed_item:
                            collected.append(parsed_item)
                    if collected:
                        break
            if not collected and getattr(detail, "best_result", None):
                best_item = parse_best_result(detail.best_result)
                if best_item:
                    collected.append(best_item)
            result.results = collected

        return result
    except Exception as exc:
        logger.error(f"识别任务执行失败 [{entry}]: {exc}")
        return None
