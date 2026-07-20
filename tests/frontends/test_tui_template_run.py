from __future__ import annotations

from mluascript.control.workspace import normalize_template_meta
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
