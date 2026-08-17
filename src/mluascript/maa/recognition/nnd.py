from __future__ import annotations

import numpy as np

from maa.pipeline import JNeuralNetworkDetect, JRecognitionType

from ..lifecycle.runtime import MaaContext
from .service import resolve_resource_reference, run_recognition_direct


def find_nnd(
    context: MaaContext,
    entry: str,
    model: str,
    targets: str | list[str] | None = None,
    roi: list[int] | None = None,
    image: np.ndarray | None = None,
):
    param = JNeuralNetworkDetect(model=resolve_resource_reference(context, model))
    if targets:
        if isinstance(targets, str):
            param.labels = [t.strip() for t in targets.split("|") if t.strip()]
        else:
            param.labels = targets
    if roi is not None:
        param.roi = (roi[0], roi[1], roi[2], roi[3])

    result = run_recognition_direct(context, entry, JRecognitionType.NeuralNetworkDetect, param, all_results=True, image=image)
    return result.to_dict(include_results=True) if result is not None else None
