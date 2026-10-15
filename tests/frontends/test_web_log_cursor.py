from __future__ import annotations

import asyncio
import importlib
import json
import weakref

import pytest

from mluascript.frontends.web import app as web_app
from mluascript.shared.logging.logger import LogBufferManager, LogEntry


@pytest.fixture
def logs(monkeypatch):
    manager = LogBufferManager()
    module = importlib.import_module('mluascript.shared.logging.logger')
    monkeypatch.setattr(module, 'log_buffer_manager', manager)

    async def no_wait(seconds):
        pass

    monkeypatch.setattr(web_app.asyncio, 'sleep', no_wait)
    return manager


def append(manager, text, *, channel='default', session='test'):
    entry = LogEntry(timestamp='same time', level='INFO', source='test', session_label=session,
                     channel=channel, message=text, formatted=text)
    manager.append(entry)
    return entry.to_dict()


class Connected:
    async def is_disconnected(self):
        return False


def event(value):
    name, data = value.strip().split('\ndata: ', 1)
    return name.removeprefix('event: '), json.loads(data)


def test_identical_log_text_is_delivered_again_after_snapshot(logs):
    first = append(logs, 'same text')

    async def scenario():
        stream = web_app.stream_logs(Connected()).body_iterator
        try:
            assert event(await anext(stream)) == ('snapshot', {'items': [first]})
            second = append(logs, 'same text')
            assert event(await anext(stream)) == ('log', second)
        finally:
            await stream.aclose()

    asyncio.run(scenario())


def test_stream_does_not_retain_evicted_log_text(logs):
    class TrackedText(str):
        pass

    references = []

    async def scenario():
        stream = web_app.stream_logs(Connected(), replay=0).body_iterator
        try:
            assert event(await anext(stream)) == ('snapshot', {'items': []})
            for index in range(3000):
                text = TrackedText(f'log-{index}')
                references.append(weakref.ref(text))
                append(logs, text)
                assert event(await anext(stream))[0] == 'log'
                assert event(await anext(stream))[0] == 'heartbeat'
            assert sum(reference() is not None for reference in references) <= logs.maxlen
        finally:
            await stream.aclose()

    asyncio.run(scenario())


def test_delta_reads_all_retained_logs_in_a_burst(logs):
    async def scenario():
        stream = web_app.stream_logs(Connected(), replay=0).body_iterator
        try:
            await anext(stream)
            expected = [append(logs, f'log-{index}') for index in range(150)]
            for item in expected:
                assert event(await anext(stream)) == ('log', item)
            assert event(await anext(stream))[0] == 'heartbeat'
        finally:
            await stream.aclose()

    asyncio.run(scenario())


def test_clearing_logs_does_not_hide_subsequent_identical_text(logs):
    first = append(logs, 'same text')

    async def scenario():
        stream = web_app.stream_logs(Connected()).body_iterator
        try:
            assert event(await anext(stream)) == ('snapshot', {'items': [first]})
            logs.clear()
            second = append(logs, 'same text')
            assert event(await anext(stream)) == ('log', second)
        finally:
            await stream.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize('replay', [0, 2])
def test_snapshot_replay_limit_does_not_leak_older_history_into_delta(logs, replay):
    history = [append(logs, f'history-{index}') for index in range(5)]

    async def scenario():
        stream = web_app.stream_logs(Connected(), replay=replay).body_iterator
        try:
            assert event(await anext(stream)) == ('snapshot', {'items': history[-replay:] if replay else []})
            assert event(await anext(stream))[0] == 'heartbeat'
            new = append(logs, 'new')
            assert event(await anext(stream)) == ('log', new)
        finally:
            await stream.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize('params, channel, session', [
    ({'channel': 'wanted'}, 'wanted', 'other'),
    ({'sessionLabel': 'wanted'}, 'other', 'wanted'),
    ({'channel': 'ignored', 'sessionLabel': 'wanted'}, 'other', 'wanted'),
])
def test_stream_keeps_channel_and_session_filtering(logs, params, channel, session):
    append(logs, 'unrelated', channel='other', session='other')

    async def scenario():
        stream = web_app.stream_logs(Connected(), **params).body_iterator
        try:
            assert event(await anext(stream)) == ('snapshot', {'items': []})
            item = append(logs, 'matching', channel=channel, session=session)
            assert event(await anext(stream)) == ('log', item)
            assert event(await anext(stream))[0] == 'heartbeat'
            append(logs, 'unrelated again', channel='other', session='other')
            assert event(await anext(stream))[0] == 'heartbeat'
        finally:
            await stream.aclose()

    asyncio.run(scenario())
