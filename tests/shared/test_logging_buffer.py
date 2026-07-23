from __future__ import annotations

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
