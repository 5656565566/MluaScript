from __future__ import annotations

from pathlib import Path

import pytest
from lupa import LuaRuntime

from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.control.workspace.template_lua_emitter import (
    _is_safe_lua_identifier,
    _lua_global_ref_expr,
    _python_to_lua_literal,
)
from mluascript.control.workspace.template_store import TemplateStore
from mluascript.control.workspace.template_models import SavedFlowConfig, TemplateSavedConfig
from mluascript.control.workspace.template_normalizer import normalize_template_meta


def test_template_store_reads_project_root_readme(tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "main.lua"
    script.parent.mkdir(parents=True)
    script.write_text("return true\n", encoding="utf-8")
    (tmp_path / "mluascript.yaml").write_text("type: lua-package\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# 项目说明\n", encoding="utf-8")

    readme = TemplateStore(WorkspaceManager(tmp_path)).get_readme("scripts/main.lua")

    assert readme is not None
    assert readme["name"] == "README.md"
    assert readme["path"] == "README.md"
    assert readme["markdown"].splitlines() == ["# 项目说明"]


def test_template_store_loads_meta_and_builds_runtime_payload_with_conditional_fields(tmp_path: Path) -> None:
    script = tmp_path / "demo.lua"
    script.write_text(
        "\n".join(
            [
                "-- @mlua-template:start",
                "-- {",
                "--   \"vars\": {",
                "--     \"useDrug\": { \"t\": \"是否吃药\", \"tp\": \"bool\", \"def\": false, \"children\": [{ \"k\": \"drugCount\", \"t\": \"数量\", \"tp\": \"int\", \"def\": 1 }] },",
                "--     \"stage\": { \"t\": \"关卡\", \"tp\": \"str\", \"def\": \"1-7\" },",
                "--     \"payload\": { \"t\": \"扩展配置\", \"tp\": \"json\", \"def\": {} }",
                "--   },",
                "--   \"tasks\": [{ \"k\": \"battle\", \"fn\": \"run_battle\", \"args\": [\"stage\", \"useDrug\", \"drugCount\", \"payload\"] }],",
                "--   \"flows\": [{ \"k\": \"main\", \"steps\": [{ \"k\": \"s1\", \"task\": \"battle\" }] }]",
                "-- }",
                "-- @mlua-template:end",
                "function run_battle(args) return args end",
            ]
        ),
        encoding="utf-8",
    )
    store = TemplateStore(WorkspaceManager(tmp_path))
    meta = store.get_template_meta("demo.lua")
    assert meta is not None

    saved = TemplateSavedConfig(
        scriptPath="demo.lua",
        selectedFlowKey="main",
        flows={
            "main": SavedFlowConfig(
                stepArgs={"s1": {"useDrug": False, "drugCount": 9, "payload": "{\"mode\": \"safe\"}"}},
                stepEnabled={"s1": True},
                stepOrder=["s1"],
            )
        },
    )

    runtime = store.build_runtime_payload(meta, saved, flow_key="main")

    assert runtime["steps"][0]["fn"] == "run_battle"
    assert runtime["steps"][0]["args"] == {
        "stage": "1-7",
        "useDrug": False,
        "payload": {"mode": "safe"},
    }

    saved.flows["main"].stepArgs["s1"]["useDrug"] = True
    runtime = store.build_runtime_payload(meta, saved, flow_key="main")
    assert runtime["steps"][0]["args"]["drugCount"] == 9


def test_template_store_builds_single_task_runtime_script(tmp_path: Path) -> None:
    meta = normalize_template_meta(
        {
            "vars": {"value": {"tp": "int", "def": 1}},
            "tasks": [{"k": "single", "fn": "run_single", "args": ["value"]}],
        }
    )
    saved = TemplateSavedConfig(scriptPath="demo.lua", tasks={"single": {"params": {"value": 7}}})

    runtime_script = TemplateStore(WorkspaceManager(tmp_path)).build_task_runtime_script(
        meta,
        saved,
        task_key="single",
    )

    assert "run_single" in runtime_script
    assert "value = 7" in runtime_script


def test_template_store_scopes_parameter_relations_to_each_task(tmp_path: Path) -> None:
    meta = normalize_template_meta(
        {
            "vars": {
                "test": {"tp": "bool", "def": False},
                "gugu": {"tp": "str", "def": "default"},
            },
            "tasks": [
                {
                    "k": "task_a",
                    "fn": "run_a",
                    "args": ["test", {"k": "gugu", "if": {"k": "test", "eq": True}}],
                },
                {"k": "task_b", "fn": "run_b", "args": ["gugu"]},
            ],
            "flows": [
                {
                    "k": "main",
                    "steps": [
                        {"k": "a1", "task": "task_a"},
                        {"k": "b1", "task": "task_b"},
                    ],
                }
            ],
        }
    )
    saved = TemplateSavedConfig(
        scriptPath="demo.lua",
        flows={
            "main": SavedFlowConfig(
                stepArgs={
                    "a1": {"test": False, "gugu": "A"},
                    "b1": {"gugu": "B"},
                }
            )
        },
    )
    store = TemplateStore(WorkspaceManager(tmp_path))

    runtime = store.build_runtime_payload(meta, saved, flow_key="main")

    assert runtime["steps"][0]["args"] == {"test": False}
    assert runtime["steps"][1]["args"] == {"gugu": "B"}

    saved.flows["main"].stepArgs["a1"]["test"] = True
    runtime = store.build_runtime_payload(meta, saved, flow_key="main")
    assert runtime["steps"][0]["args"] == {"test": True, "gugu": "A"}


def test_template_store_persists_saved_config(tmp_path: Path) -> None:
    script = tmp_path / "demo.lua"
    script.write_text("print('demo')", encoding="utf-8")
    store = TemplateStore(WorkspaceManager(tmp_path))

    saved = store.save_saved_config("demo.lua", {"selectedFlowKey": "main"})
    loaded = store.load_saved_config("demo.lua")
    saved_path = Path(store.get_saved_config_path("demo.lua"))

    assert saved.scriptPath == "demo.lua"
    assert loaded.selectedFlowKey == "main"
    assert saved_path.exists()
    assert saved_path.parent == tmp_path / "config"


def test_template_store_resolves_step_bindings_and_generates_goto(tmp_path: Path) -> None:
    script = tmp_path / "binding.lua"
    script.write_text(
        "\n".join(
            [
                "-- @mlua-template:start",
                "-- {",
                '--   "vars": { "stage": { "tp": "str", "def": "1-7" }, "retry": { "tp": "int", "def": 2 } },',
                '--   "tasks": [{ "k": "battle", "fn": "run_battle", "args": ["stage", "retry"] }],',
                '--   "flows": [{ "k": "main", "g": ["stage"], "steps": [',
                '--     { "k": "battle_1", "task": "battle", "args": { "stage": { "$bind": "var", "key": "stage" }, "retry": { "$bind": "literal", "value": 3 } }, "onSuccess": "goto", "successGoto": "battle_2", "onFail": "goto", "goto": "battle_2" },',
                '--     { "k": "battle_2", "task": "battle", "onSuccess": "exit" }',
                "--   ] }]",
                "-- }",
                "-- @mlua-template:end",
                "function run_battle(args) return args end",
            ]
        ),
        encoding="utf-8",
    )
    store = TemplateStore(WorkspaceManager(tmp_path))
    meta = store.get_template_meta("binding.lua")
    assert meta is not None
    saved = TemplateSavedConfig(
        scriptPath="binding.lua",
        flows={"main": SavedFlowConfig(globals={"stage": "2-1"})},
    )

    runtime = store.build_runtime_payload(meta, saved, flow_key="main")
    runtime_script = store.build_runtime_script(meta, saved, flow_key="main")

    assert runtime["steps"][0]["args"] == {"stage": "2-1", "retry": 3}
    assert runtime["steps"][0]["onSuccess"] == "goto"
    assert runtime["steps"][0]["successGoto"] == "battle_2"
    assert runtime["steps"][0]["goto"] == "battle_2"
    assert runtime["steps"][1]["onSuccess"] == "exit"
    assert "goto __mlua_template_step_2" in runtime_script
    assert "if 'exit' == \"exit\" then" in runtime_script


def test_template_store_executes_success_goto_and_exit(tmp_path: Path) -> None:
    script = tmp_path / "success_transition.lua"
    script.write_text(
        "\n".join(
            [
                "-- @mlua-template:start",
                "-- {",
                '--   "tasks": [',
                '--     { "k": "one", "fn": "step_one" },',
                '--     { "k": "two", "fn": "step_two" },',
                '--     { "k": "three", "fn": "step_three" },',
                '--     { "k": "four", "fn": "step_four" }',
                "--   ],",
                '--   "flows": [{ "k": "main", "steps": [',
                '--     { "k": "s1", "task": "one", "onSuccess": "goto", "successGoto": "s3" },',
                '--     { "k": "s2", "task": "two" },',
                '--     { "k": "s3", "task": "three", "onSuccess": "exit" },',
                '--     { "k": "s4", "task": "four" }',
                "--   ] }]",
                "-- }",
                "-- @mlua-template:end",
                'trace = ""',
                'function step_one(args) trace = trace .. "1" end',
                'function step_two(args) trace = trace .. "2" end',
                'function step_three(args) trace = trace .. "3" end',
                'function step_four(args) trace = trace .. "4" end',
                "function log_info(message) end",
                "function log_error(message) end",
            ]
        ),
        encoding="utf-8",
    )
    store = TemplateStore(WorkspaceManager(tmp_path))
    meta = store.get_template_meta("success_transition.lua")
    assert meta is not None
    runtime_script = store.build_runtime_script(
        meta,
        TemplateSavedConfig(scriptPath="success_transition.lua"),
        flow_key="main",
    )

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        "shared = { values = {} }; "
        "function shared.set_key(key, value) shared.values[key] = value end; "
        "function shared.get_key(key) return shared.values[key] end"
    )
    lua.execute(script.read_text(encoding="utf-8") + "\n" + runtime_script)

    assert lua.globals().trace == "13"


def test_template_store_executes_workflow_parameter_branch_and_locked_order(tmp_path: Path) -> None:
    meta = normalize_template_meta(
        {
            "vars": {"count": {"tp": "int", "def": 1}},
            "tasks": [
                {"k": "one", "fn": "step_one"},
                {"k": "two", "fn": "step_two"},
                {"k": "three", "fn": "step_three"},
            ],
            "flows": [
                {
                    "k": "main",
                    "g": ["count"],
                    "lockSteps": True,
                    "steps": [
                        {
                            "k": "s1",
                            "task": "one",
                            "successBranches": [{"if": {"k": "count", "gt": 2}, "goto": "s3"}],
                        },
                        {"k": "s2", "task": "two", "enabled": False},
                        {"k": "s3", "task": "three"},
                    ],
                }
            ],
        }
    )
    saved = TemplateSavedConfig(
        scriptPath="branch.lua",
        flows={
            "main": SavedFlowConfig(
                globals={"count": 3},
                stepOrder=["s3", "s2", "s1"],
                stepEnabled={"s1": False, "s2": True, "s3": False},
            )
        },
    )
    store = TemplateStore(WorkspaceManager(tmp_path))

    runtime = store.build_runtime_payload(meta, saved, flow_key="main")
    runtime_script = store.build_runtime_script(meta, saved, flow_key="main")

    assert [step["key"] for step in runtime["steps"]] == ["s1", "s2", "s3"]
    assert [step["enabled"] for step in runtime["steps"]] == [True, False, True]
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        "shared = { values = {} }; "
        "function shared.set_key(key, value) shared.values[key] = value end; "
        "function shared.get_key(key) return shared.values[key] end; "
        "trace = ''; "
        "function step_one(args) trace = trace .. '1' end; "
        "function step_two(args) trace = trace .. '2' end; "
        "function step_three(args) trace = trace .. '3' end; "
        "function log_info(message) end; function log_error(message) end"
    )
    lua.execute(runtime_script)

    assert lua.globals().trace == "13"
    assert lua.globals().shared["values"]["template_workflow_globals"]["count"] == 3
    assert lua.globals().shared["values"]["template_state"]["status"] == "success"


def test_python_to_lua_literal_and_runtime_script_generation(tmp_path: Path) -> None:
    assert _python_to_lua_literal(True) == "true"
    assert _python_to_lua_literal("a\n\"b") == '"a\\n\\"b"'
    assert _python_to_lua_literal({"x": 1, "ok": False}).startswith("{ ")
    assert _python_to_lua_literal({"测试": 1}) == '{ ["测试"] = 1 }'
    assert _is_safe_lua_identifier("run_battle") is True
    assert _is_safe_lua_identifier("未命名") is False
    assert _lua_global_ref_expr("run_battle") == '_G["run_battle"]'
    assert _lua_global_ref_expr("foo.bar") == '_G["foo"]["bar"]'
    assert _lua_global_ref_expr("未命名") == '_G["_E6_9C_AA_E5_91_BD_E5_90_8D"]'

    script = tmp_path / "demo.lua"
    script.write_text(
        "\n".join(
            [
                "-- @mlua-template:start",
                "-- {",
                "--   \"vars\": { \"stage\": { \"t\": \"关卡\", \"tp\": \"str\", \"def\": \"1-7\" } },",
                "--   \"tasks\": [{ \"k\": \"battle\", \"fn\": \"未命名\", \"args\": [\"stage\"] }],",
                "--   \"flows\": [{ \"k\": \"main\", \"steps\": [{ \"k\": \"s1\", \"task\": \"battle\" }] }],",
                "--   \"entry\": { \"flow\": \"main\" }",
                "-- }",
                "-- @mlua-template:end",
                "function _E6_9C_AA_E5_91_BD_E5_90_8D(args) return args end",
            ]
        ),
        encoding="utf-8",
    )
    store = TemplateStore(WorkspaceManager(tmp_path))
    meta = store.get_template_meta("demo.lua")
    assert meta is not None
    runtime_script = store.build_runtime_script(meta, TemplateSavedConfig(scriptPath="demo.lua"), flow_key="main")

    assert "local __mlua_template_args_1 =" in runtime_script
    assert 'local __mlua_template_fn_1 = _G["_E6_9C_AA_E5_91_BD_E5_90_8D"]' in runtime_script
    assert "pcall(__mlua_template_fn_1, __mlua_template_args_1)" in runtime_script
    assert "log_error('[template] step failed:" in runtime_script


def test_python_to_lua_literal_quotes_lua_reserved_keys() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)

    for key in ("local", "function", "end", "goto"):
        literal = _python_to_lua_literal({key: 1})
        result = lua.execute("return " + literal)

        assert literal == f'{{ ["{key}"] = 1 }}'
        assert result[key] == 1


def test_template_store_preserves_runtime_payload_contract() -> None:
    meta = normalize_template_meta(
        {
            "vars": {"count": {"tp": "int", "def": 1}},
            "tasks": [{"k": "one", "fn": "step_one"}],
            "flows": [
                {
                    "k": "main",
                    "g": ["count"],
                    "steps": [
                        {
                            "k": "s1",
                            "task": "one",
                            "successBranches": [{"if": {"k": "count", "gt": 2}, "goto": "s1"}],
                        }
                    ],
                }
            ],
        }
    )

    runtime = TemplateStore().build_runtime_payload(meta, TemplateSavedConfig(), flow_key="main")

    assert runtime == {
        "flowKey": "main",
        "steps": [
            {
                "key": "s1",
                "task": "one",
                "fn": "step_one",
                "enabled": True,
                "args": {},
                "successBranches": [{"if": {"k": "count", "gt": 2, "in": []}, "goto": "s1"}],
                "onSuccess": "continue",
                "successGoto": "",
                "onFail": "stop",
                "goto": "",
            }
        ],
        "globals": {"count": 1},
        "lockSteps": False,
    }


def test_template_store_rejects_step_with_missing_task() -> None:
    meta = normalize_template_meta(
        {
            "flows": [
                {
                    "k": "main",
                    "steps": [{"k": "missing", "task": "no_such_task"}],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="missing.*no_such_task"):
        TemplateStore().build_runtime_payload(meta, TemplateSavedConfig(), flow_key="main")


@pytest.mark.parametrize(
    ("transition_fields", "missing_target"),
    [
        ({"onSuccess": "goto", "successGoto": "missing_success"}, "missing_success"),
        ({"onFail": "goto", "goto": "missing_failure"}, "missing_failure"),
    ],
)
def test_template_store_rejects_missing_transition_target(
    transition_fields: dict[str, str],
    missing_target: str,
) -> None:
    meta = normalize_template_meta(
        {
            "tasks": [{"k": "one", "fn": "step_one"}],
            "flows": [
                {
                    "k": "main",
                    "steps": [{"k": "s1", "task": "one", **transition_fields}],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match=f"s1.*{missing_target}"):
        TemplateStore().build_runtime_script(meta, TemplateSavedConfig(), flow_key="main")
