from __future__ import annotations

from maa.pipeline import JOCR, JRecognitionType

from ..lifecycle.runtime import MaaContext
from .service import run_recognition_direct


import numpy as np


def find_ocr(
    context: MaaContext,
    entry: str,
    expected: str | list[str] | None = None,
    roi: list[int] | None = None,
    image: np.ndarray | None = None,
):
    param = JOCR()
    if expected is not None:
        param.expected = [expected] if isinstance(expected, str) else expected
    if roi is not None:
        param.roi = (roi[0], roi[1], roi[2], roi[3])

    result = run_recognition_direct(context, entry, JRecognitionType.OCR, param, image=image)
    return result.to_dict() if result is not None else None


def find_ocr_all(
    context: MaaContext,
    entry: str,
    expected: str | list[str] | None = None,
    roi: list[int] | None = None,
    image: np.ndarray | None = None,
):
    param = JOCR()
    if expected is not None:
        param.expected = [expected] if isinstance(expected, str) else expected
    if roi is not None:
        param.roi = (roi[0], roi[1], roi[2], roi[3])

    result = run_recognition_direct(context, entry, JRecognitionType.OCR, param, all_results=True, image=image)
    return result.to_dict(include_results=True) if result is not None else None
