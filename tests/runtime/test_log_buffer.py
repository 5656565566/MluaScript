from __future__ import annotations

import pytest

from mluascript.runtime.log_buffer import TaskLogBuffer


def test_task_log_buffer_keeps_latest_entries() -> None:
    buffer = TaskLogBuffer(max_entries=3)

    buffer.extend(
        {"level": "INFO", "message": str(index)}
        for index in range(5)
    )

    assert [item["message"] for item in buffer] == ["2", "3", "4"]


def test_task_log_buffer_defaults_to_latest_200_entries() -> None:
    buffer = TaskLogBuffer()

    buffer.extend(
        {"level": "INFO", "message": str(index)}
        for index in range(201)
    )

    assert len(buffer) == 200
    assert buffer[0]["message"] == "1"
    assert buffer[-1]["message"] == "200"


def test_task_log_buffer_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        TaskLogBuffer(max_entries=0)
