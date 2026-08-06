from __future__ import annotations

from mluascript.control.workspace import normalize_template_meta
from mluascript.frontends.tui.components.pagination import paginate_items
from mluascript.frontends.tui.screens.template_run import _build_task_field_rows


def test_tui_task_fields_support_object_refs_and_recursive_activation() -> None:
    meta = normalize_template_meta(
        {
            "vars": {
                "root": {"tp": "bool", "def": False},
                "child": {"tp": "bool", "def": True},
                "leaf": {"tp": "str", "def": "value"},
            },
            "tasks": [
                {
                    "k": "run",
                    "args": [
                        {"k": "leaf", "if": {"k": "child", "eq": True}},
                        "root",
                        {"k": "child", "if": {"k": "root", "eq": True}},
                    ],
                }
            ],
        }
    )
    task = meta.tasks[0]

    hidden_rows = _build_task_field_rows(task.args, meta.vars, {"root": False, "child": True})
    assert [(row.field.k, row.depth, row.active) for row in hidden_rows] == [
        ("root", 0, True),
        ("child", 1, False),
        ("leaf", 2, False),
    ]

    visible_rows = _build_task_field_rows(task.args, meta.vars, {"root": True, "child": True})
    assert [(row.field.k, row.depth, row.active) for row in visible_rows] == [
        ("root", 0, True),
        ("child", 1, True),
        ("leaf", 2, True),
    ]


def test_tui_template_tasks_paginate_ten_per_page() -> None:
    items = list(range(23))

    first, first_index, total_pages = paginate_items(items, 0, 10)
    last, last_index, _ = paginate_items(items, 99, 10)

    assert first == list(range(10))
    assert first_index == 0
    assert total_pages == 3
    assert last == [20, 21, 22]
    assert last_index == 2
