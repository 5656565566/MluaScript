import asyncio
import base64
import io
import struct
import zlib
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from mluascript.frontends.web import app as web_app
from mluascript.shared.config.models import WebServerConfig


IMAGE_LIMIT = 10 * 1024 * 1024
BODY_LIMIT = 16 * 1024 * 1024


def _png():
    output = io.BytesIO()
    Image.new("RGB", (3, 5), (12, 34, 56)).save(output, format="PNG")
    return output.getvalue()


def _png_header(width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    settings = WebServerConfig(
        password="secret-pass", session_secret="0123456789abcdef",
        project_roots=[str(tmp_path / "projects")],
    )
    monkeypatch.setattr(web_app, "_get_web_config", lambda: settings)
    context = SimpleNamespace(tasker=object())
    facade = SimpleNamespace(device_facade=SimpleNamespace(_maa_facade=SimpleNamespace(context=context)))
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    monkeypatch.setattr(web_app, "initialize_maa_runtime", lambda value: value)
    monkeypatch.setattr(web_app, "find_ocr", lambda *_args, **_kwargs: {"hit": True})
    result = TestClient(web_app.create_web_app(tmp_path / "dist", runtime_dir=tmp_path, script_roots=[]))
    assert result.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"}).status_code == 200
    return result


def test_normal_data_url_still_reaches_recognition_as_contiguous_bgr(client, monkeypatch):
    images = []
    monkeypatch.setattr(web_app, "find_ocr", lambda *_args, **kwargs: images.append(kwargs["image"]) or {"hit": True})
    response = client.post("/api/projects/test/recognize-image", json={
        "imageBase64": "data:image/png;base64," + base64.b64encode(_png()).decode(),
    })
    assert response.status_code == 200
    assert images[0].shape == (5, 3, 3)
    assert images[0][0, 0].tolist() == [56, 34, 12]
    assert images[0].flags.c_contiguous


@pytest.mark.parametrize("extra, status", [(0, 200), (1, 413)])
def test_base64_images_enforce_the_exact_decoded_byte_limit(client, extra, status):
    raw = _png().ljust(IMAGE_LIMIT + extra, b"\x00")
    response = client.post("/api/projects/test/recognize-image", json={"imageBase64": base64.b64encode(raw).decode()})
    assert response.status_code == status


def test_encoded_image_limit_is_checked_before_base64_decode(mocker):
    decode = mocker.spy(web_app.base64, "b64decode")
    with pytest.raises(HTTPException) as error:
        web_app._recognition_image_array(None, "test", web_app.ProjectImageRecognitionPayload(
            imageBase64="A" * (((IMAGE_LIMIT + 2) // 3) * 4 + 4),
        ))
    assert error.value.status_code == 413
    decode.assert_not_called()


def test_large_project_file_is_rejected_before_reading(monkeypatch, tmp_path, mocker):
    image_path = tmp_path / "large.png"
    with image_path.open("wb") as output:
        output.truncate(IMAGE_LIMIT + 1)
    monkeypatch.setattr(web_app, "_recognition_resource_path", lambda *_args: str(image_path))
    read = mocker.spy(Path, "open")
    with pytest.raises(HTTPException) as error:
        web_app._recognition_image_array(None, "test", web_app.ProjectImageRecognitionPayload(imagePath="large.png"))
    assert error.value.status_code == 413
    read.assert_not_called()


@pytest.mark.parametrize("width, height", [(5001, 4000), (100000, 100000)])
def test_large_dimensions_are_rejected_before_pixel_decode(client, mocker, width, height):
    convert = mocker.patch.object(Image.Image, "convert", side_effect=AssertionError("pixel decode must not run"))
    response = client.post("/api/projects/test/recognize-image", json={
        "imageBase64": base64.b64encode(_png_header(width, height)).decode(),
    })
    assert response.status_code == 413
    convert.assert_not_called()


def test_pixel_limit_allows_the_exact_boundary(client, mocker):
    convert = mocker.patch.object(Image.Image, "convert", return_value=Image.new("RGB", (1, 1)))
    response = client.post("/api/projects/test/recognize-image", json={
        "imageBase64": base64.b64encode(_png_header(5000, 4000)).decode(),
    })
    assert response.status_code == 200
    convert.assert_called_once_with("RGB")


def test_declared_oversized_body_is_rejected_before_parsing(client, mocker):
    recognize = mocker.spy(web_app, "_recognition_image_array")
    response = client.post(
        "/api/projects/test/recognize-image", content=b"{}",
        headers={"content-type": "application/json", "content-length": str(BODY_LIMIT + 1)},
    )
    assert response.status_code == 413
    recognize.assert_not_called()


def test_chunked_body_limit_is_enforced_without_content_length(client, mocker):
    recognize = mocker.spy(web_app, "_recognition_image_array")

    async def scenario():
        async def chunks():
            yield b'{"imageBase64":"'
            for _ in range(17):
                yield b"A" * (1024 * 1024)
            yield b'"}'

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="http://testserver", cookies=client.cookies) as requester:
            response = await requester.post(
                "/api/projects/test/recognize-image", content=chunks(), headers={"content-type": "application/json"},
            )
        assert response.status_code == 413

    asyncio.run(scenario())
    recognize.assert_not_called()


def test_invalid_image_remains_a_client_error(client):
    response = client.post("/api/projects/test/recognize-image", json={"imageBase64": "invalid base64"})
    assert response.status_code == 400


@pytest.mark.parametrize("extra, status", [(0, 200), (1, 413)])
def test_request_body_limit_has_an_inclusive_boundary(client, extra, status):
    body = b'{"imageBase64":"' + base64.b64encode(_png()) + b'"}'
    response = client.post(
        "/api/projects/test/recognize-image", content=body.ljust(BODY_LIMIT + extra, b" "),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == status


def test_other_routes_do_not_inherit_the_recognition_request_limit(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret-pass"},
        headers={"content-length": str(BODY_LIMIT + 1)},
    )
    assert response.status_code == 200


def test_only_two_recognitions_run_at_once_and_other_routes_remain_available(client, monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        saturated = asyncio.Event()
        release = Event()
        lock = Lock()
        active = peak = calls = 0

        def recognize(*_args, **_kwargs):
            nonlocal active, peak, calls
            with lock:
                active += 1
                calls += 1
                peak = max(peak, active)
                if active == 2:
                    loop.call_soon_threadsafe(saturated.set)
            try:
                assert release.wait(timeout=5)
                return {"hit": True}
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(web_app, "find_ocr", recognize)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="http://testserver", cookies=client.cookies) as requester:
            jobs = [asyncio.create_task(requester.post(
                "/api/projects/test/recognize-image", json={"imageBase64": base64.b64encode(_png()).decode()},
            )) for _ in range(8)]
            try:
                await asyncio.wait_for(saturated.wait(), timeout=3)
                assert (await requester.get("/api/auth/status")).status_code == 200
                with lock:
                    assert calls == 2
            finally:
                release.set()
                responses = await asyncio.gather(*jobs)
            assert all(response.status_code == 200 for response in responses)
        assert peak == 2
        assert calls == 8

    asyncio.run(scenario())
