from __future__ import annotations

import json
from pathlib import Path

from lupa.lua54 import LuaRuntime
from pydantic import BaseModel

from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.image_bridge import build_runtime_image_handle
from mluascript.runtime.llm.decider import AIDecider
from mluascript.runtime.llm.models import OpenAITool
from mluascript.runtime.llm.prompt import build_decision_messages, build_tool_specs
from mluascript.runtime.threading import RuntimeThreadManager, build_thread_exports
from mluascript.runtime.utils.table_lua import lua_2_python

import pytest


class _HostAPI:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.stop_checks = 0

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def print(self, message: str) -> None:
        _ = message

    def notify(self, message: str) -> None:
        _ = message

    def check_stop(self) -> None:
        self.stop_checks += 1


class ShipmentCreated(BaseModel):
    order_id: str
    status: str
    insured_amount: float | bool | None = None



def test_engine_executes_real_lua_with_host_log() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        log_message("info", "hello from lua")
        return 41 + 1
        '''
    )

    assert result == 42
    assert ("info", "hello from lua") in host.logs
    assert host.stop_checks >= 1



def test_engine_executes_real_lua_with_shared_value() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        local box = shared.value({ count = 1 })
        box:set_key("count", box:get_key("count") + 4)
        return box:get_key("count")
        '''
    )

    assert result == 5



def test_engine_executes_real_lua_with_thread_spawn() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        function worker_task()
            return 99
        end

        local task = thread.spawn("worker_task")
        task:join(1.0)
        return {
            result = task:result(),
            error = task:error(),
            status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert isinstance(normalized, dict)
    assert normalized["result"] == 99, normalized
    assert normalized["error"] in ("", None), normalized



def test_engine_executes_real_lua_with_dynamic_namespace_in_main_and_subruntime() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)
    engine.register_namespace(
        "maa",
        lambda _: {
            "device_name": lambda: "demo-device",
        },
    )

    result = engine.execute(
        '''
        function worker_task()
            return maa.device_name()
        end

        local task = thread.spawn("worker_task")
        task:join(1.0)
        return {
            main = maa.device_name(),
            child = task:result(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert normalized == {
        "main": "demo-device",
        "child": "demo-device",
    }


def test_engine_subthread_maa_namespace_failure_does_not_break_main_runtime() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    def _explode() -> str:
        raise RuntimeError("maa namespace exploded")

    engine.register_namespace(
        "maa",
        lambda _: {
            "explode": _explode,
            "device_name": lambda: "demo-device",
        },
    )

    result = engine.execute(
        '''
        function worker_task()
            return maa.explode()
        end

        local task = thread.spawn("worker_task")
        task:join(1.0)
        return {
            child_error = task:error(),
            child_result = task:result(),
            main = maa.device_name(),
            status = task:status(),
        }
        '''
    )

    normalized = lua_2_python(result)
    assert "child_result" not in normalized, normalized
    assert "maa namespace exploded" in str(normalized["child_error"]), normalized
    assert normalized["status"]["done"] is True, normalized
    assert normalized["status"]["alive"] is False, normalized
    assert normalized["main"] == "demo-device", normalized



def test_build_thread_exports_with_engine_subruntime_builder() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)
    engine.inject()

    assert engine.lupa is not None
    exports = build_thread_exports(engine.lupa, RuntimeThreadManager(), build_subruntime=engine._build_subruntime)

    assert exports is not None



def test_thread_exports_require_string_function_name() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    with pytest.raises(ValueError):
        exports.spawn(lambda: 1)  # type: ignore[arg-type]



def test_thread_exports_missing_named_function_reports_error() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    manager = RuntimeThreadManager()
    exports = build_thread_exports(lua, manager)

    with pytest.raises(ValueError):
        exports.spawn("missing_function")


def test_engine_main_runtime_busy_loop_stops_after_host_request() -> None:
    import threading
    import time

    class _StopHostAPI(_HostAPI):
        def __init__(self) -> None:
            super().__init__()
            self.stop_requested = False

        def check_stop(self) -> None:
            self.stop_checks += 1
            if self.stop_requested:
                raise RuntimeError("stop requested")

    host = _StopHostAPI()
    engine = LuaEngine(Path("."), host)
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            engine.execute(
                '''
                local n = 0
                while true do
                    n = n + 1
                end
                '''
            )
        except Exception as exc:
            outcome["error"] = str(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    time.sleep(0.1)
    host.stop_requested = True
    thread.join(0.3)

    assert thread.is_alive() is False
    assert "stop requested" in str(outcome.get("error", ""))



def test_ai_decider_add_screenshot_encodes_runtime_image_handle_into_extra_image_url() -> None:
    image = build_runtime_image_handle(__import__("numpy").zeros((10, 20, 3), dtype=__import__("numpy").uint8))
    decider = AIDecider()

    decider.add_screenshot(image)

    item = decider.inputs[0]
    assert item.kind == "image"
    assert item.value is image
    assert item.extra["mime_type"] == "image/png"
    assert item.extra["width"] == 20
    assert item.extra["height"] == 10
    assert str(item.extra["image_url"]).startswith("data:image/png;base64,")



def test_build_decision_messages_uses_extra_image_url_for_image_input() -> None:
    image = build_runtime_image_handle(__import__("numpy").zeros((5, 6, 3), dtype=__import__("numpy").uint8))
    decider = AIDecider()
    decider.add_screenshot(image)

    messages = build_decision_messages("demo", decider._normalize_inputs(), [], [], 0, 0)
    payload = json.loads(messages[1]["content"])

    assert payload["inputs"][0]["kind"] == "image"
    assert payload["inputs"][0]["value"].startswith("data:image/png;base64,")
    assert payload["inputs"][0]["extra"]["mime_type"] == "image/png"



def test_build_tool_specs_supports_complete_openai_tool_schema() -> None:
    decider = AIDecider()
    tool = OpenAITool.model_validate(
        {
            "type": "function",
            "function": {
                "name": "create_advanced_shipment",
                "strict": False,
                "description": "创建一个货运订单，支持多物品、时间窗口、保险等高级选项",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "唯一订单号，格式：ORD-YYYYMMDD-XXXX",
                        },
                        "origin": {
                            "type": "object",
                            "description": "发货起点信息",
                            "properties": {
                                "address": {"type": "string"},
                                "city": {"type": "string"},
                                "country": {"type": "string", "default": "CN"},
                            },
                            "required": ["address", "city"],
                        },
                        "destination": {
                            "$ref": "#/properties/origin",
                        },
                        "items": {
                            "type": "array",
                            "description": "发货物品列表",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sku": {"type": "string"},
                                    "quantity": {"type": "integer", "minimum": 1},
                                    "weight_kg": {"type": "number", "minimum": 0},
                                    "fragile": {"type": "boolean", "default": False},
                                },
                                "required": ["sku", "quantity"],
                            },
                        },
                        "insurance": {
                            "anyOf": [
                                {"type": "null"},
                                {"type": "number", "minimum": 0},
                            ],
                        },
                    },
                    "required": ["order_id", "origin", "destination", "items"],
                },
            },
        }
    )
    decider.register_info_source(
        handler=lambda **_: {"status": "ok"},
        name="create_advanced_shipment",
        openai_tool=tool,
    )

    specs = build_tool_specs(decider._info_sources())

    assert len(specs) == 1
    assert specs[0]["function"]["strict"] is False
    assert specs[0]["function"]["parameters"]["properties"]["destination"]["$ref"] == "#/properties/origin"
    assert specs[0]["function"]["parameters"]["properties"]["insurance"]["anyOf"][1]["type"] == "number"



def test_ai_decider_validates_tool_result_with_pydantic_v2_model() -> None:
    decider = AIDecider()
    decider.register_info_source(
        handler=lambda: {"order_id": "ORD-20250501-0001", "status": "created", "insured_amount": 1999.0},
        name="create_advanced_shipment",
        result_model=ShipmentCreated,
    )

    record = decider._call_member(decider.members[0], {})

    assert record.success is True
    assert record.result == {
        "order_id": "ORD-20250501-0001",
        "status": "created",
        "insured_amount": 1999.0,
    }
    assert record.result_validation_error == ""



def test_ai_decider_marks_validation_failure_when_tool_result_shape_is_invalid() -> None:
    decider = AIDecider()
    decider.register_info_source(
        handler=lambda: {"status": "created"},
        name="create_advanced_shipment",
        result_model=ShipmentCreated,
    )

    record = decider._call_member(decider.members[0], {})

    assert record.success is False
    assert record.result == {"status": "created"}
    assert "order_id" in record.result_validation_error



def test_ai_decider_validates_tool_result_with_json_schema() -> None:
    decider = AIDecider()
    decider.register_info_source(
        handler=lambda: [{"sku": "SKU-1", "quantity": 2, "weight_kg": 1.5}],
        name="create_advanced_shipment",
        result_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "weight_kg": {"type": "number"},
                },
                "required": ["sku", "quantity", "weight_kg"],
            },
        },
    )

    record = decider._call_member(decider.members[0], {})

    assert record.success is True
    assert record.result == [{"sku": "SKU-1", "quantity": 2, "weight_kg": 1.5}]
    assert record.result_validation_error == ""



def test_ai_decider_marks_json_schema_validation_failure() -> None:
    decider = AIDecider()
    decider.register_info_source(
        handler=lambda: [{"sku": "SKU-1", "quantity": "bad"}],
        name="create_advanced_shipment",
        result_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                },
                "required": ["sku", "quantity"],
            },
        },
    )

    record = decider._call_member(decider.members[0], {})

    assert record.success is False
    assert "result[0].quantity" in record.result_validation_error



def test_lua_decider_add_info_supports_returns_schema() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        local decider = llm.new_decider()

        local function create_advanced_shipment_handler(order_id, origin, destination, items)
            return items
        end

        local shipment_item = {
            type = "object",
            properties = {
                sku = { type = "string" },
                quantity = { type = "integer" },
                weight_kg = { type = "number" },
            },
            required = { "sku", "quantity", "weight_kg" },
        }

        decider:add_info({
            name = "create_advanced_shipment_handler",
            title = "创建高级货运订单",
            description = "创建高级货运订单",
            handler = create_advanced_shipment_handler,
            properties = {
                order_id = { type = "string" },
                origin = { type = "object" },
                destination = { ["$ref"] = "#/properties/origin" },
                items = {
                    type = "array",
                    items = shipment_item,
                },
            },
            required = { "order_id", "origin", "destination", "items" },
            returns = {
                type = "array",
                items = shipment_item,
            },
        })

        local member = decider._decider.members[0]
        return {
            member_id = member.id,
            title = member.title,
            description = member.description,
            tool_name = member.openai_tool["function"].name,
            return_type = member.result_schema.type,
            item_type = member.result_schema.items.type,
        }
        '''
    )

    normalized = lua_2_python(result)
    assert normalized == {
        "member_id": "create_advanced_shipment_handler",
        "title": "创建高级货运订单",
        "description": "创建高级货运订单",
        "tool_name": "create_advanced_shipment_handler",
        "return_type": "array",
        "item_type": "object",
    }



def test_lua_decider_add_executor_supports_parameter_schema_only() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        local decider = llm.new_decider()

        local function submit_order(order_id, force)
            return true
        end

        decider:add_executor({
            name = "submit_order",
            title = "提交订单",
            description = "确认后提交订单",
            handler = submit_order,
            properties = {
                order_id = { type = "string" },
                force = { type = "boolean" },
            },
            required = { "order_id" },
        })

        local member = decider._decider.members[0]
        return {
            member_id = member.id,
            title = member.title,
            description = member.description,
            tool_name = member.openai_tool["function"].name,
            has_result_schema = member.result_schema ~= nil,
            member_kind = member.kind,
        }
        '''
    )

    normalized = lua_2_python(result)
    assert normalized == {
        "member_id": "submit_order",
        "title": "提交订单",
        "description": "确认后提交订单",
        "tool_name": "submit_order",
        "has_result_schema": False,
        "member_kind": "executor",
    }



def test_lua_info_member_validates_lua_table_result_against_object_schema() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        local decider = llm.new_decider()

        local function get_runtime_state()
            return {
                scene = "battle_prepare",
                energy = 12,
                has_potion = true,
            }
        end

        decider:add_info({
            name = "get_runtime_state",
            title = "获取运行状态",
            description = "获取当前场景与体力信息",
            handler = get_runtime_state,
            returns = {
                type = "object",
                properties = {
                    scene = { type = "string" },
                    energy = { type = "integer" },
                    has_potion = { type = "boolean" },
                },
                required = { "scene", "energy", "has_potion" },
            },
        })

        local member = decider._decider.members[0]
        local record = decider._decider:_call_member(member, {})
        return {
            success = record.success,
            result = record.result,
            error = record.error,
            result_validation_error = record.result_validation_error,
        }
        '''
    )

    normalized = lua_2_python(result)
    assert normalized == {
        "success": True,
        "result": {
            "scene": "battle_prepare",
            "energy": 12,
            "has_potion": True,
        },
        "error": "",
        "result_validation_error": "",
    }
