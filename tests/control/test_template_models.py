from __future__ import annotations

import pytest

from mluascript.control.workspace import (
    TemplateParseError,
    dump_template_block,
    is_condition_active,
    normalize_template_meta,
    parse_template_meta,
)


def test_normalize_template_meta_flattens_children_and_option_children() -> None:
    meta = normalize_template_meta(
        {
            "id": "demo",
            "vars": {
                "useDrug": {
                    "t": "是否吃药",
                    "tp": "bool",
                    "children": [
                        {
                            "k": "drugCount",
                            "t": "吃药数量",
                            "tp": "int",
                            "def": 1,
                        }
                    ],
                },
                "energy": {
                    "t": "补体力",
                    "tp": "enum",
                    "oneOf": [
                        {"v": "none", "t": "不用"},
                        {
                            "v": "stone",
                            "t": "碎石",
                            "children": [
                                {
                                    "k": "stoneCount",
                                    "t": "石头数量",
                                    "tp": "int",
                                    "def": 1,
                                }
                            ],
                        },
                    ],
                },
            },
            "tasks": [
                {
                    "k": "battle",
                    "fn": "run_battle",
                    "args": ["useDrug", "drugCount", "energy", "stoneCount"],
                }
            ],
            "flows": [
                {
                    "k": "main",
                    "steps": [
                        {"k": "s1", "task": "battle"},
                    ],
                }
            ],
        }
    )

    assert set(meta.vars.keys()) == {"useDrug", "drugCount", "energy", "stoneCount"}
    task_args = {arg if isinstance(arg, str) else arg.k: arg for arg in meta.tasks[0].args}
    assert task_args["drugCount"].if_ is not None
    assert task_args["drugCount"].if_.k == "useDrug"
    assert task_args["drugCount"].if_.eq is True
    assert task_args["stoneCount"].if_ is not None
    assert task_args["stoneCount"].if_.k == "energy"
    assert task_args["stoneCount"].if_.eq == "stone"
    assert [option.v for option in meta.vars["energy"].one_of] == ["none", "stone"]
    assert meta.entry.flow == "main"
    assert meta.entry.task == "battle"


def test_is_condition_active_supports_typed_comparisons() -> None:
    assert is_condition_active({"k": "mode", "eq": "safe"}, {"mode": "safe"}) is True
    assert is_condition_active({"k": "mode", "ne": "fast"}, {"mode": "safe"}) is True
    assert is_condition_active({"k": "mode", "in": ["safe", "debug"]}, {"mode": "debug"}) is True
    assert is_condition_active({"k": "count", "gt": 2}, {"count": 3}) is True
    assert is_condition_active({"k": "count", "gte": 3}, {"count": 3}) is True
    assert is_condition_active({"k": "ratio", "lt": 1.5}, {"ratio": 1.25}) is True
    assert is_condition_active({"k": "ratio", "lte": 1.25}, {"ratio": 1.25}) is True
    assert is_condition_active({"k": "count", "gt": 2}, {"count": "invalid"}) is False
    assert is_condition_active({"k": "enabled"}, {"enabled": True}) is True
    assert is_condition_active({"k": "enabled"}, {"enabled": False}) is False


def test_template_variable_types_use_canonical_set_and_path_ui_hint() -> None:
    meta = normalize_template_meta(
        {
            "vars": {
                "ratio": {"tp": "num", "def": 0.5},
                "payload": {"tp": "json", "def": {"mode": "safe"}},
                "file": {"tp": "str", "ui": "path"},
            }
        }
    )

    assert meta.vars["ratio"].tp == "num"
    assert meta.vars["payload"].tp == "json"
    assert meta.vars["file"].tp == "str"
    assert meta.vars["file"].ui == "path"


@pytest.mark.parametrize("removed_type", ["path", "list", "obj"])
def test_template_variable_removed_types_are_rejected(removed_type: str) -> None:
    with pytest.raises(ValueError):
        normalize_template_meta({"vars": {"legacy": {"tp": removed_type}}})


def test_path_ui_hint_is_rejected_for_non_string_type() -> None:
    with pytest.raises(ValueError, match="ui 仅适用于 str 字段"):
        normalize_template_meta({"vars": {"invalid": {"tp": "json", "ui": "path"}}})


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["test", {"k": "gugu", "if": {"k": "gugu", "eq": True}}], "不能依赖自身"),
        ([{"k": "gugu", "if": {"k": "test", "eq": True}}], "任务未引用的参数"),
    ],
)
def test_task_parameter_relations_must_stay_within_the_task(args: list[object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_template_meta(
            {
                "vars": {
                    "test": {"tp": "bool"},
                    "gugu": {"tp": "str"},
                },
                "tasks": [{"k": "task", "args": args}],
            }
        )


def test_workflow_success_branches_require_flow_parameter_and_existing_target() -> None:
    meta = normalize_template_meta(
        {
            "vars": {"count": {"tp": "int", "def": 0}},
            "tasks": [{"k": "run", "fn": "run_task"}],
            "flows": [
                {
                    "k": "main",
                    "g": ["count"],
                    "lockSteps": True,
                    "steps": [
                        {
                            "k": "check",
                            "task": "run",
                            "successBranches": [{"if": {"k": "count", "gte": 2}, "goto": "finish"}],
                        },
                        {"k": "finish", "task": "run"},
                    ],
                }
            ],
        }
    )

    assert meta.flows[0].lockSteps is True
    assert meta.flows[0].steps[0].successBranches[0].if_.gte == 2
    assert meta.flows[0].steps[0].successBranches[0].goto == "finish"

    with pytest.raises(ValueError, match="非任务流参数"):
        normalize_template_meta(
            {
                "vars": {"count": {"tp": "int"}},
                "tasks": [{"k": "run"}],
                "flows": [
                    {
                        "k": "main",
                        "steps": [
                            {
                                "k": "check",
                                "task": "run",
                                "successBranches": [{"if": {"k": "count", "eq": 1}, "goto": "check"}],
                            }
                        ],
                    }
                ],
            }
        )


def test_parse_template_meta_and_dump_template_block_roundtrip() -> None:
    script = "\n".join(
        [
            "-- @mlua-template:start",
            "-- {",
            "--   \"id\": \"demo\",",
            "--   \"vars\": {",
            "--     \"useDrug\": {",
            "--       \"t\": \"是否吃药\",",
            "--       \"tp\": \"bool\",",
            "--       \"children\": [",
            "--         { \"k\": \"drugCount\", \"t\": \"数量\", \"tp\": \"int\", \"def\": 1 }",
            "--       ]",
            "--     }",
            "--   },",
            "--   \"tasks\": [{ \"k\": \"battle\", \"fn\": \"run_battle\", \"args\": [\"useDrug\", \"drugCount\"] }],",
            "--   \"flows\": [{ \"k\": \"main\", \"steps\": [{ \"k\": \"s1\", \"task\": \"battle\" }] }]",
            "-- }",
            "-- @mlua-template:end",
            "",
            "function run_battle(args)",
            "  return args",
            "end",
        ]
    )

    source = parse_template_meta(script, script_path="demo.lua")

    assert source is not None
    assert source.script_path == "demo.lua"
    assert source.meta is not None
    task_args = {arg if isinstance(arg, str) else arg.k: arg for arg in source.meta.tasks[0].args}
    assert task_args["drugCount"].if_ is not None
    dumped = dump_template_block(source.meta)
    assert "-- @mlua-template:start" in dumped
    assert '"drugCount"' in dumped
    assert '"if"' in dumped


def test_parse_template_meta_raises_for_invalid_json() -> None:
    script = "\n".join(
        [
            "-- @mlua-template:start",
            "-- { invalid json }",
            "-- @mlua-template:end",
        ]
    )

    try:
        parse_template_meta(script)
    except TemplateParseError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("expected TemplateParseError")


def test_parse_template_meta_rejects_multiple_template_blocks() -> None:
    script = "\n".join(
        [
            "-- @mlua-template:start",
            "-- {}",
            "-- @mlua-template:start",
            "-- {}",
            "-- @mlua-template:end",
        ]
    )

    try:
        parse_template_meta(script)
    except TemplateParseError as exc:
        assert "最多配置一个模板" in str(exc)
    else:
        raise AssertionError("expected TemplateParseError")
