from __future__ import annotations

from maa.pipeline import JColorMatch, JRecognitionType

from ..lifecycle.runtime import MaaContext
from .service import run_recognition_direct


import numpy as np


def find_color(
    context: MaaContext,
    entry: str,
    lower: list[list[int]] | None = None,
    upper: list[list[int]] | None = None,
    roi: list[int] | None = None,
    image: np.ndarray | None = None,
):
    param = JColorMatch(lower=lower or [], upper=upper or [])
    if roi is not None:
        param.roi = (roi[0], roi[1], roi[2], roi[3])

    result = run_recognition_direct(context, entry, JRecognitionType.ColorMatch, param, image=image)
    return result.to_dict() if result is not None else None
