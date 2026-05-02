from __future__ import annotations

from maa.pipeline import JFeatureMatch, JRecognitionType

from ..lifecycle.runtime import MaaContext
from .service import run_recognition_direct


import numpy as np


def find_feature(
    context: MaaContext,
    entry: str,
    template: str | list[str] | None = None,
    roi: list[int] | None = None,
    image: np.ndarray | None = None,
):
    param = JFeatureMatch(template=[] if template is None else ([template] if isinstance(template, str) else template))
    if roi is not None:
        param.roi = (roi[0], roi[1], roi[2], roi[3])

    result = run_recognition_direct(context, entry, JRecognitionType.FeatureMatch, param, image=image)
    return result.to_dict() if result is not None else None
