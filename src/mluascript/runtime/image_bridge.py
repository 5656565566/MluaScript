from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image


@dataclass(slots=True)
class RuntimeImageHandle:
    image: Image.Image

    @property
    def width(self) -> int:
        return int(self.image.width)

    @property
    def height(self) -> int:
        return int(self.image.height)

    @property
    def mode(self) -> str:
        return str(self.image.mode)

    @property
    def channels(self) -> int:
        bands = self.image.getbands()
        return len(bands)

    def save(self, path: str, format: str | None = None) -> None:
        self.image.save(path, format=format)

    def crop(self, x: int, y: int, w: int, h: int) -> "RuntimeImageHandle":
        left = int(x)
        top = int(y)
        right = left + max(0, int(w))
        bottom = top + max(0, int(h))
        cropped = self.image.crop((left, top, right, bottom))
        return RuntimeImageHandle(image=cropped)

    def to_pil_image(self) -> Image.Image:
        return self.image

    def to_png_bytes(self) -> bytes:
        buffer = io.BytesIO()
        self.image.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_bgr_array(self) -> np.ndarray:
        array = np.asarray(self.image)
        if array.ndim == 2:
            return np.stack((array,) * 3, axis=-1)
        elif array.shape[2] == 3:
            return array[:, :, ::-1] # RGB to BGR
        elif array.shape[2] == 4:
            return array[:, :, :3][:, :, ::-1] # RGBA to BGR
        return array


def to_pil_image(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return image

    array = np.asarray(image)
    if array.ndim == 2:
        return Image.fromarray(array)
    if array.ndim == 3 and array.shape[2] == 3:
        return Image.fromarray(array[:, :, ::-1], mode="RGB")
    if array.ndim == 3 and array.shape[2] == 4:
        return Image.fromarray(array[:, :, [2, 1, 0, 3]], mode="RGBA")
    return Image.fromarray(array)


def build_runtime_image_handle(image: Any) -> RuntimeImageHandle:
    return RuntimeImageHandle(image=to_pil_image(image))
