from __future__ import annotations

from pathlib import Path

import pytest

from mluascript.maa.controllers.query import get_connection_label, get_resolution, get_uuid
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths


class FakeController:
    def __init__(self, resolution: tuple[int, ...], uuid: str = "fake-uuid") -> None:
        self.resolution = resolution
        self.uuid = uuid


class FakeImage:
    def __init__(self, shape: tuple[int, int, int]) -> None:
        self.shape = shape


class FakeScreencapController(FakeController):
    def __init__(self) -> None:
        super().__init__(())
        self._image = FakeImage((720, 1280, 3))

    def post_screencap(self):
        return FakeJob(self._image)


class FakeJob:
    def __init__(self, image: FakeImage) -> None:
        self.succeeded = True
        self._image = image

    def wait(self) -> "FakeJob":
        return self

    def get(self) -> FakeImage:
        return self._image


def build_context(controller=None, label: str | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(connection_label=label),
        controller=controller,
    )


def test_get_resolution_returns_controller_resolution_directly() -> None:
    context = build_context(FakeController((1280, 720)))

    assert get_resolution(context) == (1280, 720)


def test_get_resolution_falls_back_to_screencap_shape() -> None:
    context = build_context(FakeScreencapController())

    assert get_resolution(context) == (1280, 720)


def test_get_uuid_reads_controller_uuid() -> None:
    context = build_context(FakeController((1280, 720), uuid="device-1"))

    assert get_uuid(context) == "device-1"


def test_get_connection_label_returns_default_when_missing() -> None:
    context = build_context(FakeController((1280, 720)))

    assert get_connection_label(context) == "未连接"


def test_get_connection_label_returns_state_label() -> None:
    context = build_context(FakeController((1280, 720)), label="ADB:1")

    assert get_connection_label(context) == "ADB:1"
