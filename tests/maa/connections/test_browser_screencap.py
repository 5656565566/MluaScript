from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from mluascript.maa.extensions.browser.controller import BrowserController


@pytest.fixture
def controller(mocker):
    result = BrowserController.__new__(BrowserController)
    result._handle = None
    result._own = False
    result._connected = True
    result.last_error = ''
    result._current_page = mocker.Mock(return_value=mocker.Mock())
    result._submit_browser = mocker.Mock(side_effect=lambda operation: operation())
    return result


def png(color):
    buffer = io.BytesIO()
    Image.new('RGB', (32, 24), color).save(buffer, format='PNG')
    return buffer.getvalue()


def test_disconnected_browser_reports_screencap_failure(controller, mocker):
    controller._connected = False
    error = mocker.patch('mluascript.maa.extensions.browser.controller.logger.error')
    with pytest.raises(RuntimeError, match='not connected'):
        controller.screencap()
    assert 'not connected' in controller.last_error
    controller._submit_browser.assert_not_called()
    error.assert_called_once()


@pytest.mark.parametrize('failure', [
    RuntimeError('Target page has been closed'),
    PlaywrightTimeoutError('Screenshot timed out'),
])
def test_screenshot_failure_keeps_the_underlying_reason(controller, mocker, failure):
    controller._current_page().screenshot.side_effect = failure
    error = mocker.patch('mluascript.maa.extensions.browser.controller.logger.error')
    with pytest.raises(RuntimeError, match=str(failure)) as raised:
        controller.screencap()
    assert raised.value.__cause__ is failure
    assert str(failure) in controller.last_error
    error.assert_called_once()


def test_worker_timeout_without_message_still_has_a_failure_reason(controller):
    controller._submit_browser.side_effect = TimeoutError()
    with pytest.raises(RuntimeError, match='TimeoutError'):
        controller.screencap()
    assert controller.last_error


def test_invalid_screenshot_data_is_reported_as_failure(controller):
    controller._current_page().screenshot.return_value = b'not an image'
    with pytest.raises(RuntimeError, match='cannot identify image'):
        controller.screencap()
    assert 'cannot identify image' in controller.last_error


@pytest.mark.parametrize('color', [(0, 0, 0), (1, 2, 3)])
def test_valid_screenshot_preserves_black_frames_and_contiguous_bgr(controller, color):
    controller._current_page().screenshot.return_value = png(color)
    image = controller.screencap()
    assert image.shape == (24, 32, 3)
    assert image.dtype == np.uint8
    assert image.flags.c_contiguous
    assert np.all(image == color[::-1])
    controller._submit_browser.assert_called_once()


def test_successful_screencap_clears_the_previous_failure_reason(controller):
    page = controller._current_page()
    page.screenshot.side_effect = [RuntimeError('Target page has been closed'), png('black')]
    with pytest.raises(RuntimeError):
        controller.screencap()
    assert controller.last_error
    assert controller.screencap().shape == (24, 32, 3)
    assert controller.last_error == ''
