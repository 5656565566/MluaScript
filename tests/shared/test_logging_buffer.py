from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from mluascript.shared.logging.logger import LogBufferManager, LogEntry


def _entry(index: int) -> LogEntry:
    return LogEntry(
        timestamp=str(index),
        level="INFO",
        source="test",
        session_label=f"session-{index}",
        channel=f"channel-{index}",
        message=str(index),
        formatted=str(index),
    )


def test_log_buffer_manager_bounds_global_and_secondary_indexes() -> None:
    manager = LogBufferManager(maxlen=2, bucket_maxlen=2)

    for index in range(4):
        manager.append(_entry(index))

    assert [item["message"] for item in manager.list_all()] == ["2", "3"]
    assert manager.iter_sessions() == ["session-2", "session-3"]
    assert manager.list_by_channel("channel-0") == []


def test_log_buffer_manager_defaults_to_latest_200_entries() -> None:
    manager = LogBufferManager()

    for index in range(201):
        manager.append(_entry(index))

    assert len(manager.list_all()) == 200
    assert manager.list_all()[0]["message"] == "1"
    assert len(manager.iter_sessions()) == 200


def test_cursor_survives_clear_and_advances_even_for_empty_snapshots() -> None:
    manager = LogBufferManager()
    manager.append(_entry(1))
    cursor, items = manager.snapshot(limit=0)
    assert cursor == 1 and items == []
    assert manager.snapshot(channel='missing') == (cursor, [])
    manager.clear()
    assert manager.snapshot(after=cursor) == (cursor, [])
    manager.append(_entry(2))
    next_cursor, items = manager.snapshot(after=cursor)
    assert next_cursor == 2
    assert [item['message'] for item in items] == ['2']


def test_concurrent_writes_assign_unique_ordered_sequences_with_a_bounded_snapshot() -> None:
    manager = LogBufferManager()

    def write(index):
        entry = _entry(index)
        manager.append(entry)
        return entry.sequence

    with ThreadPoolExecutor(max_workers=8) as writers:
        sequences = list(writers.map(write, range(1000)))
    assert sorted(sequences) == list(range(1, 1001))
    cursor, items = manager.snapshot()
    assert cursor == 1000 and len(items) == 200
    assert len(manager.snapshot(after=990)[1]) == 10
