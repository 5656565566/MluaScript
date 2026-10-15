from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from maa.tasker import Tasker

from mluascript.control.integration import script_resources as pool
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.lifecycle import runtime as maa_runtime
from mluascript.maa.recognition.ocr import find_ocr
from mluascript.maa.types import MaaPaths


_MODEL_DIR = Path(__file__).resolve().parents[3] / "model"


@pytest.mark.integration
@pytest.mark.skipif(not (_MODEL_DIR / "ocr" / "det.onnx").is_file(), reason="Requires local Maa OCR models")
def test_native_ocr_results_survive_releasing_and_reusing_resource_handles(monkeypatch, tmp_path):
    import maa

    monkeypatch.setattr(maa_runtime, "resolve_maa_log_file", lambda runtime_dir: tmp_path / "maa.log")
    Tasker.set_log_dir(tmp_path)
    paths = MaaPaths(library_dir=Path(maa.__file__).parent / "bin", resource_dir=tmp_path / "resources", model_dir=_MODEL_DIR)
    paths.resource_dir.mkdir()
    monkeypatch.setattr(pool, "resolve_maa_paths", lambda: paths)
    monkeypatch.setattr(pool, "create_maa_context", lambda: MaaContext(paths=paths))
    pool.clear_idle_script_runtime()
    image = Image.new("RGB", (512, 160), "white")
    ImageDraw.Draw(image).text((30, 35), "TEST123", font=ImageFont.load_default(size=56), fill="black")
    array = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])
    handles = set()
    try:
        for _ in range(3):
            context = pool.acquire_script_maa_context(paths.resource_dir, None)
            try:
                handles.add((context.tasker._handle, context.resource._handle))
                result = find_ocr(context, "resource-reuse", expected="TEST123", image=array)
                assert result and result["hit"], result
            finally:
                assert pool.release_script_resources(context)
        assert len(handles) == 1
    finally:
        pool.clear_idle_script_runtime()
