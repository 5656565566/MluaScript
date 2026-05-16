from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from mluascript.shared.config.manager import load_config
from mluascript.maa.errors import MaaResourceError
from mluascript.maa.lifecycle.bootstrap import _normalize_adb_path, configure_toolkit_options, resolve_maa_paths
from mluascript.maa.lifecycle.resources import get_node_list, load_resource, override_pipeline
from mluascript.maa.lifecycle.runtime import MaaContext, create_maa_context
from mluascript.maa.types import MaaContextState, MaaPaths


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

def create_fake_maa_context():
    return MaaContext(
        MaaPaths(
            library_dir = Path(),
            resource_dir = Path()
        ),
        MaaContextState(),
    )

def test_resolve_maa_paths_uses_root_defaults_when_config_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "config.yaml"
        load_config(str(temp_path))
        paths = resolve_maa_paths(temp_path)

        assert paths.library_dir == temp_path / "maafw"
        assert paths.resource_dir == temp_path / "resource"


def test_resolve_maa_paths_uses_runtime_dir_when_root_dir_missing(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        runtime_dir = Path(temp_dir)
        load_config(str(runtime_dir / "config.yaml"))
        monkeypatch.setattr("mluascript.maa.lifecycle.bootstrap.get_runtime_dir", lambda: runtime_dir)

        paths = resolve_maa_paths()

        assert paths.library_dir == runtime_dir / "maafw"
        assert paths.resource_dir == runtime_dir / "resource"


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
