from __future__ import annotations

from pathlib import Path

from lupa import LuaRuntime

from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.control.workspace.template_store import (
    TemplateStore,
    _is_safe_lua_identifier,
    _lua_global_ref_expr,
    _python_to_lua_literal,
)
from mluascript.control.workspace.template_models import SavedFlowConfig, TemplateSavedConfig


def test_template_store_loads_meta_and_builds_runtime_payload_with_conditional_fields(tmp_path: Path) -> None:
    script = tmp_path / "demo.lua"
    script.write_text(
        "\n".join(
            [
                "-- @mlua-template:start",
                "-- {",
                "--   \"vars\": {",
                "--     \"useDrug\": { \"t\": \"是否吃药\", \"tp\": \"bool\", \"def\": false, \"children\": [{ \"k\": \"drugCount\", \"t\": \"数量\", \"tp\": \"int\", \"def\": 1 }] },",
                "--     \"stage\": { \"t\": \"关卡\", \"tp\": \"str\", \"def\": \"1-7\" }",
                "--   },",
                "--   \"tasks\": [{ \"k\": \"battle\", \"fn\": \"run_battle\", \"args\": [\"stage\", \"useDrug\", \"drugCount\"] }],",
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
                stepArgs={"s1": {"useDrug": False, "drugCount": 9}},
                stepEnabled={"s1": True},
                stepOrder=["s1"],
            )
        },
    )

    runtime = store.build_runtime_payload(meta, saved, flow_key="main")

    assert runtime["steps"][0]["fn"] == "run_battle"
    assert runtime["steps"][0]["args"] == {"stage": "1-7", "useDrug": False}

    saved.flows["main"].stepArgs["s1"]["useDrug"] = True
    runtime = store.build_runtime_payload(meta, saved, flow_key="main")
    assert runtime["steps"][0]["args"]["drugCount"] == 9


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
    lua.execute(script.read_text(encoding="utf-8") + "\n" + runtime_script)

    assert lua.globals().trace == "13"


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
