from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic

import pytest

from mluascript.maa.controllers import base
from mluascript.maa.controllers.input import click
from mluascript.maa.controllers.screen import screencap
from mluascript.maa.errors import MaaConnectionError
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaPaths
from mluascript.runtime.exception import LuaExitException
from mluascript.runtime.stopper import Stopper


class Job:
    def __init__(self, event=None, complete=lambda: None):
        self.event = event
        self.complete = complete
        self.succeeded = True

    @property
    def done(self): return self.event is None or self.event.is_set()

    def wait(self):
        if self.event is not None:
            assert self.event.wait(3)
        self.complete()
        return self

    def get(self): return None


class Controller:
    def __init__(self):
        self.connected = False
        self.uuid = 'reconnect-test'
        self.entered, self.release = Event(), Event()
        self.connections = 0
        self.clicks = 0

    def post_connection(self):
        self.connections += 1
        self.entered.set()
        return Job(self.release, lambda: setattr(self, 'connected', True))

    def post_screencap(self): return Job()

    def post_click(self, x, y):
        self.clicks += 1
        return Job()


def context(controller):
    return MaaContext(paths=MaaPaths(library_dir=Path('.'), resource_dir=Path('.')), controller=controller)


def test_reconnect_does_not_hold_operation_lock_and_other_operations_fail_promptly():
    controller = Controller()
    first, second = context(controller), context(controller)
    with ThreadPoolExecutor(max_workers=1) as callers:
        pending = callers.submit(click, first, 1, 2)
        try:
            assert controller.entered.wait(1)
            lock = base._controller_operation_lock(controller)
            assert lock.acquire(blocking=False)
            lock.release()
            start = monotonic()
            with pytest.raises(MaaConnectionError, match='reconnect'):
                screencap(second)
            with pytest.raises(MaaConnectionError, match='reconnect'):
                click(second, 3, 4)
            assert monotonic() - start < 0.5
            assert controller.connections == 1
        finally:
            controller.release.set()
        assert pending.result(2) is True
    assert controller.clicks == 1


def test_timed_out_connection_is_retained_and_resumed_without_duplicate_post(monkeypatch):
    monkeypatch.setattr(base, '_RECONNECT_TIMEOUT_SECONDS', 0.03)
    controller = Controller()
    try:
        with pytest.raises(MaaConnectionError, match='timed out'):
            click(context(controller), 1, 2)
        with pytest.raises(MaaConnectionError, match='reconnect'):
            click(context(controller), 1, 2)
        assert controller.connections == 1
    finally:
        controller.release.set()
    assert click(context(controller), 1, 2)
    assert controller.connections == 1


def test_stop_interrupts_reconnect_wait_without_starting_another_native_job():
    controller = Controller()
    ctx = context(controller)
    stopper = Stopper()
    ctx.state.extras['check_stop'] = stopper.check
    with ThreadPoolExecutor(max_workers=1) as callers:
        pending = callers.submit(click, ctx, 1, 2)
        try:
            assert controller.entered.wait(1)
            stopper.request_stop()
            with pytest.raises(LuaExitException):
                pending.result(1)
            assert controller.connections == 1
        finally:
            controller.release.set()


def test_cancelled_operation_waiting_for_the_lock_never_posts_a_click():
    controller = Controller()
    controller.connected = True
    ctx, stopper, checked = context(controller), Stopper(), Event()

    def check():
        stopper.check()
        checked.set()

    ctx.state.extras['check_stop'] = check
    lock = base._controller_operation_lock(controller)
    with ThreadPoolExecutor(max_workers=1) as callers:
        lock.acquire()
        try:
            pending = callers.submit(click, ctx, 1, 2)
            assert checked.wait(1)
            stopper.request_stop()
        finally:
            lock.release()
        with pytest.raises(LuaExitException):
            pending.result(1)
    assert controller.clicks == 0
