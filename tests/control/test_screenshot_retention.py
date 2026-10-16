import base64
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mluascript.control.devices.facade import DeviceFacade
from mluascript.control.devices.models import DeviceActionResult, DeviceOverview


@pytest.fixture
def screenshots(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    facade = DeviceFacade.__new__(DeviceFacade)
    facade._capture_current_screenshot_result = lambda: DeviceActionResult(
        ok=True, message="截图成功", image_base64=base64.b64encode(b"captured-png").decode(),
    )
    facade.get_overview = lambda: DeviceOverview()
    return facade, tmp_path / "temp" / "screenshots"


def _old_screenshots(directory, count):
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for index in range(count):
        path = directory / f"screenshot_20261001_120000_{index:032x}.png"
        path.write_bytes(b"old-png")
        os.utime(path, (1000 + index, 1000 + index))
        files.append(path)
    return files


def test_new_screenshots_keep_the_latest_100_and_leave_legacy_and_unrelated_files(screenshots):
    facade, directory = screenshots
    files = _old_screenshots(directory, 102)
    legacy = directory.parent / "screenshot_20260901_120000.png"
    legacy.write_bytes(b"user-saved")
    unrelated = directory / "keep.png"
    unrelated.write_bytes(b"user-image")
    nested = directory / "nested"
    nested.mkdir()
    (nested / files[0].name).write_bytes(b"nested-image")

    result = facade.screencap_current_and_save()

    assert result.ok
    current = Path(result.saved_path)
    assert current.parent.resolve() == directory
    assert current.read_bytes() == b"captured-png"
    assert all(not path.exists() for path in files[:3])
    assert all(path.exists() for path in files[3:])
    assert len(list(directory.glob("screenshot_*.png"))) == 100
    assert legacy.read_bytes() == b"user-saved"
    assert unrelated.read_bytes() == b"user-image"
    assert (nested / files[0].name).read_bytes() == b"nested-image"


def test_concurrent_captures_have_distinct_names_and_stay_within_the_retention_limit(screenshots):
    facade, directory = screenshots
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: facade.screencap_current_and_save(), range(110)))
    assert all(result.ok for result in results)
    assert len({result.saved_path for result in results}) == 110
    assert len(list(directory.glob("screenshot_*.png"))) == 100


def test_cleanup_failure_preserves_the_new_capture_and_reports_a_warning(screenshots, monkeypatch):
    facade, directory = screenshots
    files = _old_screenshots(directory, 100)
    unlink = Path.unlink

    def fail_oldest(path, *args, **kwargs):
        if path.resolve() == files[0]:
            raise PermissionError("file is in use")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_oldest)
    result = facade.screencap_current_and_save()
    assert result.ok
    assert result.severity == "warning"
    assert "清理" in result.message
    assert Path(result.saved_path).read_bytes() == b"captured-png"


def test_failed_capture_creates_no_screenshot_directory(screenshots):
    facade, directory = screenshots
    facade._capture_current_screenshot_result = lambda: DeviceActionResult(ok=False, message="capture failed")
    assert not facade.screencap_current_and_save().ok
    assert not directory.exists()


def test_failed_write_removes_its_partial_file(screenshots, monkeypatch):
    facade, directory = screenshots
    write = Path.write_bytes

    def fail_write(path, data):
        write(path, data[:2])
        raise OSError("disk is full")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    result = facade.screencap_current_and_save()
    assert not result.ok
    assert not list(directory.glob("*.png"))
