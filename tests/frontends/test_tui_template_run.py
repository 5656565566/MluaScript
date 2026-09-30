from __future__ import annotations

from mluascript.control.workspace import normalize_template_meta
from mluascript.control.workspace.artifact_service import RunnableArtifact
from mluascript.frontends.tui.components.pagination import paginate_items
from mluascript.frontends.tui.screens.run import _matches_artifact_query
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


def test_tui_artifact_search_covers_package_metadata() -> None:
    artifact = RunnableArtifact(
        id="artifact-id",
        kind="package",
        name="每日任务",
        path="scripts/daily.mlspkg",
        mtime=1,
        description="领取奖励",
        author="Tester",
        version="1.2.3",
        package_id="com.example.daily",
        entrypoint="main",
        artifact_path="F:/runtime/scripts/daily.mlspkg",
    )

    for query in ("每日", "scripts/daily", "奖励", "tester", "1.2.3", "com.example.daily", "main"):
        assert _matches_artifact_query(artifact, query)
    assert not _matches_artifact_query(artifact, "missing")


def test_readme_heading_slug_keeps_cjk_titles() -> None:
    """纯中文标题不能被 slug 抹成空串，否则 README 内的 #锚点 跳转永远失败"""

    from mluascript.frontends.tui.screens.template_run import _slugify_heading

    assert _slugify_heading("第二节") == "第二节"
    assert _slugify_heading("安装说明") == "安装说明"
    assert _slugify_heading("二重螺旋") == "二重螺旋"
    assert _slugify_heading("快速开始 Quick Start") == "快速开始-quick-start"
    assert _slugify_heading("配置/config.yaml") == "配置-config-yaml"
    assert _slugify_heading("  A  B  ") == "a-b"
    assert _slugify_heading("###") == ""


def test_textual_builtin_slug_cannot_handle_cjk() -> None:
    """记录上游行为：Textual 自带 slug 会把 CJK 当非语言字符整个删掉"""

    from textual._slug import slug

    assert slug("第二节") == ""
    assert slug("Second Section") == "second-section"
