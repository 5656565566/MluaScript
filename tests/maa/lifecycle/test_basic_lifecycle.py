from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from mluascript.shared.config.manager import load_config
from mluascript.maa.errors import MaaResourceError
from mluascript.maa.lifecycle.bootstrap import (
    _normalize_adb_path,
    configure_toolkit_options,
    resolve_maa_log_dir,
    resolve_maa_paths,
)
from mluascript.maa.lifecycle.resources import get_node_list, load_resource, override_pipeline
from mluascript.maa.lifecycle.runtime import MaaContext, create_maa_context
from mluascript.maa.types import MaaContextState, MaaPaths
from mluascript.shared.logging import configure_file_logging


class FakeBundleJob:
    def __init__(self) -> None:
        self.wait_called = False

    def wait(self) -> "FakeBundleJob":
        self.wait_called = True
        return self


class FakeResource:
    def __init__(self) -> None:
        self.bundle_calls: list[str] = []
        self.override_calls: list[dict[str, object]] = []
        self.node_list = ["node_a", "node_b"]
        self.raise_on_bundle = False
        self.last_job: FakeBundleJob | None = None

    def post_bundle(self, path: str) -> FakeBundleJob:
        if self.raise_on_bundle:
            raise RuntimeError("bundle failed")
        self.bundle_calls.append(path)
        self.last_job = FakeBundleJob()
        return self.last_job

    def override_pipeline(self, override: dict[str, object]) -> bool:
        self.override_calls.append(override)
        return True


@pytest.fixture(autouse=True)
def _cleanup_file_logging():
    yield
    configure_file_logging(None)


@contextmanager
def temp_runtime_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            yield Path(temp_dir)
        finally:
            configure_file_logging(None)

def create_fake_maa_context():
    return MaaContext(
        MaaPaths(
            library_dir = Path(),
            resource_dir = Path()
        ),
        MaaContextState(),
    )

def test_resolve_maa_paths_uses_root_defaults_when_config_missing() -> None:
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"
        load_config(str(temp_path))
        paths = resolve_maa_paths(temp_path)

        assert paths.library_dir == temp_path / "maafw"
        assert paths.resource_dir == temp_path / "resource"


def test_resolve_maa_paths_uses_runtime_dir_when_root_dir_missing(monkeypatch) -> None:
    with temp_runtime_dir() as runtime_dir:
        load_config(str(runtime_dir / "config.yaml"))
        monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.get_runtime_dir", lambda: runtime_dir)

        paths = resolve_maa_paths()

        assert paths.library_dir == runtime_dir / "maafw"
        assert paths.resource_dir == runtime_dir / "resource"


def test_resolve_maa_log_dir_uses_runtime_dir_default(monkeypatch) -> None:
    with temp_runtime_dir() as runtime_dir:
        load_config(str(runtime_dir / "config.yaml"))
        monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.get_runtime_dir", lambda: runtime_dir)

        log_dir = resolve_maa_log_dir()

        assert log_dir == (runtime_dir / "logs" / "maa").resolve()


def test_configure_toolkit_options_contains_adb_path_when_present() -> None:
    paths = MaaPaths(library_dir=Path("."), resource_dir=Path("."), adb_path=Path("adb.exe"))

    options = configure_toolkit_options(paths)

    assert options == {"adb_path": "adb.exe"}


def test_normalize_adb_path_uses_platform_specific_binary_name_for_windows(monkeypatch) -> None:
    monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.platform.system", lambda: "Windows")

    assert _normalize_adb_path("C:/tools/platform-tools") == Path("C:/tools/platform-tools/adb.exe")


def test_normalize_adb_path_uses_platform_specific_binary_name_for_linux(monkeypatch) -> None:
    monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.platform.system", lambda: "Linux")

    assert _normalize_adb_path("/usr/bin") == Path("/usr/bin/adb")


def test_load_resource_returns_true_when_resource_missing() -> None:
    context = create_fake_maa_context()

    assert load_resource(context) is True


def test_load_resource_calls_bundle_when_resource_present() -> None:
    resource = FakeResource()
    context = create_fake_maa_context()
    context.resource = resource

    result = load_resource(context, "resource_dir")

    assert result is True
    assert resource.bundle_calls == ["resource_dir"]
    assert resource.last_job is not None
    assert resource.last_job.wait_called is True


def test_load_resource_raises_resource_error_on_failure() -> None:
    resource = FakeResource()
    resource.raise_on_bundle = True
    context = create_fake_maa_context()
    context.resource = resource

    try:
        load_resource(context, "broken")
    except MaaResourceError as exc:
        assert "Failed to load resource" in str(exc)
    else:
        raise AssertionError("expected MaaResourceError")


def test_override_pipeline_returns_false_when_resource_missing() -> None:
    context = create_fake_maa_context()

    assert override_pipeline(context, {"demo": 1}) is False


def test_override_pipeline_delegates_to_resource() -> None:
    resource = FakeResource()
    context = create_fake_maa_context()
    context.resource = resource

    result = override_pipeline(context, {"demo": 1})

    assert result is True
    assert resource.override_calls == [{"demo": 1}]


def test_get_node_list_returns_empty_when_resource_missing() -> None:
    context = create_fake_maa_context()

    assert get_node_list(context) == []


def test_get_node_list_reads_resource_node_list() -> None:
    resource = FakeResource()
    context = create_fake_maa_context()
    context.resource = resource

    assert get_node_list(context) == ["node_a", "node_b"]


def test_create_maa_context_enables_tasker_log_dir(monkeypatch) -> None:
    with temp_runtime_dir() as runtime_dir:
        load_config(str(runtime_dir / "config.yaml"))

        calls: dict[str, object] = {}

        monkeypatch.setattr("mluascript.maa.lifecycle.runtime.get_runtime_dir", lambda: runtime_dir)
        monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.get_runtime_dir", lambda: runtime_dir)
        monkeypatch.setattr(
            "mluascript.maa.lifecycle.runtime.Toolkit",
            SimpleNamespace(init_option=lambda path: calls.setdefault("toolkit_init_option", path)),
        )
        monkeypatch.setattr(
            "mluascript.maa.lifecycle.runtime.Tasker",
            SimpleNamespace(
                set_log_dir=lambda path: calls.setdefault("set_log_dir", Path(path)) or True,
                set_stdout_level=lambda level: calls.setdefault("set_stdout_level", level) or True,
            ),
        )

        context = create_maa_context()

        assert context.paths.library_dir == runtime_dir / "maafw"
        assert calls["toolkit_init_option"] == str(runtime_dir)
        assert calls["set_log_dir"] == (runtime_dir / "logs" / "maa").resolve()
        assert "set_stdout_level" in calls
