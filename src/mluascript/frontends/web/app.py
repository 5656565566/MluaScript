from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mluascript.control.facade import get_control_facade
from mluascript.control.workspace import TemplateSavedConfig, get_template_store
from mluascript.shared.logging import get_logs, get_logs_by_channel, get_logs_by_session

device_router = APIRouter(prefix="/api/device")
editor_router = APIRouter(prefix="/api/editor")
logs_router = APIRouter(prefix="/api/logs")
streams_router = APIRouter(prefix="/api/streams")
system_router = APIRouter(prefix="/api/system")
run_router = APIRouter(prefix="/api/run")


class WorkspaceSyncPayload(BaseModel):
    workspaceXml: str = ""
    luaCode: str = ""


class EditorSessionPayload(BaseModel):
    blocklyDocument: dict[str, Any] = Field(default_factory=dict)
    luaDocument: dict[str, Any] = Field(default_factory=dict)


class BlocklyFileCreatePayload(BaseModel):
    path: str
    xml: str = ""


class BlocklyFileUpdatePayload(BaseModel):
    path: str
    xml: str = ""
    expectedMtime: float | None = None


class LuaFileCreatePayload(BaseModel):
    path: str
    content: str = ""


class LuaFileUpdatePayload(BaseModel):
    path: str
    content: str = ""
    expectedMtime: float | None = None


class ValidateNamePayload(BaseModel):
    path: str


class ConnectAdbPayload(BaseModel):
    address: str = ""


class ConnectDevicePayload(BaseModel):
    actionId: str = ""


class DeviceDiscoverPayload(BaseModel):
    kind: str = ""


class DeviceConnectPayload(BaseModel):
    deviceId: str = ""


class RunLuaPayload(BaseModel):
    sessionLabel: str | None = None
    luaCode: str = ""
    scriptPath: str | None = None


class RunPipelinePayload(BaseModel):
    entry: str
    override: dict[str, Any] | None = None
    sessionLabel: str | None = None
    projectPath: str = ""


class RunTemplatePayload(BaseModel):
    mode: str = "workflow"
    scriptPath: str
    workflowKey: str = ""
    workflow: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


_EDITOR_SESSION: dict[str, Any] = {
    "blocklyDocument": {
        "xml": "",
        "filename": "",
        "path": "",
        "mtime": None,
        "dirty": False,
        "saveMode": "create",
    },
    "luaDocument": {
        "content": "",
        "filename": "",
        "path": "",
        "mtime": None,
        "dirty": False,
        "saveMode": "create",
    },
}


def _ok(data: Any, message: str = "", meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "message": message,
        "meta": meta or {},
    }


def _editor_root() -> Path:
    root = Path.cwd() / ".mluascript_web"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _editor_blockly_root() -> Path:
    root = _editor_root() / "blockly"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _editor_lua_root() -> Path:
    root = _editor_root() / "lua"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalize_editor_file_path(raw_path: str, *, kind: str) -> tuple[Path, str]:
    normalized = str(raw_path or "").strip().replace("\\", "/")
    if not normalized:
        raise HTTPException(status_code=400, detail="路径不能为空")

    if kind == "blockly":
        base = _editor_blockly_root()
        if not normalized.endswith(".xml"):
            normalized = f"{normalized}.xml"
    else:
        base = _editor_lua_root()
        if not normalized.endswith(".lua"):
            normalized = f"{normalized}.lua"

    relative = normalized.lstrip("/")
    target = (base / relative).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="路径超出 editor 存储范围") from exc
    return target, relative.replace("\\", "/")


def _list_editor_files(kind: str) -> list[dict[str, Any]]:
    base = _editor_blockly_root() if kind == "blockly" else _editor_lua_root()
    suffix = ".xml" if kind == "blockly" else ".lua"
    items: list[dict[str, Any]] = []
    for file in sorted(base.rglob(f"*{suffix}")):
        if not file.is_file():
            continue
        items.append(
            {
                "name": file.name,
                "path": str(file.relative_to(base)).replace("\\", "/"),
                "mtime": file.stat().st_mtime,
            }
        )
    return items


def _read_editor_file(path_text: str, *, kind: str) -> dict[str, Any]:
    target, relative = _normalize_editor_file_path(path_text, kind=kind)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    content = target.read_text(encoding="utf-8")
    payload_key = "xml" if kind == "blockly" else "content"
    return {
        "path": relative,
        "filename": target.name,
        payload_key: content,
        "mtime": target.stat().st_mtime,
        "saveMode": "update",
    }


def _create_editor_file(path_text: str, content: str, *, kind: str) -> dict[str, Any]:
    target, relative = _normalize_editor_file_path(path_text, kind=kind)
    if target.exists():
        raise HTTPException(status_code=409, detail="目标文件已存在")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "path": relative,
        "filename": target.name,
        "mtime": target.stat().st_mtime,
        "saveMode": "update",
    }


def _update_editor_file(path_text: str, content: str, expected_mtime: float | None, *, kind: str) -> dict[str, Any]:
    target, relative = _normalize_editor_file_path(path_text, kind=kind)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="目标文件不存在")
    if expected_mtime is not None:
        current_mtime = target.stat().st_mtime
        if abs(current_mtime - expected_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="文件已发生变化，请刷新后重试")
    target.write_text(content, encoding="utf-8")
    return {
        "path": relative,
        "filename": target.name,
        "mtime": target.stat().st_mtime,
        "saveMode": "update",
    }


def _validate_editor_name(path_text: str, *, kind: str) -> dict[str, Any]:
    target, relative = _normalize_editor_file_path(path_text, kind=kind)
    return {
        "path": relative,
        "available": not target.exists(),
        "reason": "already_exists" if target.exists() else "ok",
    }


def _build_log_items(limit: int, channel: str | None, session_label: str | None) -> list[dict[str, Any]]:
    if session_label:
        return get_logs_by_session(session_label, limit=limit)
    if channel:
        return get_logs_by_channel(channel, limit=limit)
    return get_logs(limit=limit)



def _serialize_device_page_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return items



def _build_device_items_payload() -> list[dict[str, Any]]:
    overview = get_control_facade().get_device_overview()
    buckets = [overview.adb.items, overview.emulator.items, overview.browser.items, overview.win32.items]
    items: list[dict[str, Any]] = []
    for bucket in buckets:
        for item in bucket:
            items.append(item.model_dump())
    return items



def _build_device_session_payload() -> dict[str, Any]:
    overview = get_control_facade().get_device_overview()
    return overview.connection.model_dump()


@device_router.get("/overview")
def get_device_overview() -> dict[str, Any]:
    overview = get_control_facade().get_device_overview()
    return _ok({"item": overview.model_dump()})


@device_router.get("/items")
def get_device_items(kind: str | None = None) -> dict[str, Any]:
    items = _build_device_items_payload()
    if kind:
        items = [item for item in items if str(item.get("kind") or "") == kind]
    return _ok({"items": _serialize_device_page_items(items), "count": len(items)})


@device_router.post("/discover")
def discover_devices(payload: DeviceDiscoverPayload) -> dict[str, Any]:
    facade = get_control_facade()
    kind = payload.kind.strip().lower()
    if kind == "adb":
        result = facade.find_adb_devices()
    elif kind == "win32":
        result = facade.find_win32_windows()
    else:
        raise HTTPException(status_code=400, detail="unsupported device kind")
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "设备发现失败")
    return _ok(
        {
            "message": result.message,
            "overview": (result.overview or facade.get_device_overview()).model_dump(),
            "items": _build_device_items_payload(),
        },
        message=result.message,
    )


@device_router.post("/connect")
def connect_device(payload: DeviceConnectPayload) -> dict[str, Any]:
    facade = get_control_facade()
    result = facade.connect_device(payload.deviceId)
    overview = result.overview or facade.get_device_overview()
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "设备连接失败")
    return _ok(
        {
            "message": result.message,
            "connection": overview.connection.model_dump(),
        },
        message=result.message,
    )


@device_router.post("/adb/connect-manual")
def connect_adb_manual(payload: ConnectAdbPayload) -> dict[str, Any]:
    facade = get_control_facade()
    result = facade.connect_adb(payload.address)
    overview = result.overview or facade.get_device_overview()
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "ADB 连接失败")
    return _ok(
        {
            "message": result.message,
            "connection": overview.connection.model_dump(),
        },
        message=result.message,
    )


@device_router.get("/session")
def get_device_session() -> dict[str, Any]:
    return _ok({"item": _build_device_session_payload()})


@device_router.post("/disconnect")
def disconnect_device() -> dict[str, Any]:
    facade = get_control_facade()
    result = facade.disconnect_device()
    overview = result.overview or facade.get_device_overview()
    session = overview.connection.model_dump()
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "断开设备失败")
    return _ok(
        {
            "message": result.message,
            "sessions": [session] if session.get("label") else [],
        },
        message=result.message,
    )


@device_router.post("/screencap")
def screencap_device() -> dict[str, Any]:
    result = get_control_facade().screencap_current_device()
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "截图失败")
    return _ok(
        {
            "message": result.message,
            "imageBase64": result.image_base64,
        },
        message=result.message,
    )


@system_router.get("/health")
def system_health() -> dict[str, Any]:
    return _ok({"service": "mluascript_web", "version": "1.0.0", "status": "up"})


@system_router.get("/bootstrap")
def system_bootstrap() -> dict[str, Any]:
    facade = get_control_facade()
    system_state = facade.get_system_state().model_dump()
    overview = facade.get_device_overview().model_dump()

    adb_items = []
    for idx, item in enumerate(facade.device_facade._adb_raw):
        adb_items.append({
            "id": f"adb:{idx}",
            "kind": "adb",
            "title": str(item.get("name") or "未命名设备"),
            "subtitle": str(item.get("address") or "未知地址"),
            "enabled": True,
            "tags": [],
        })
    overview["adb"]["items"] = adb_items
    
    win32_items = []
    for idx, item in enumerate(facade.device_facade._win32_raw):
        hwnd = int(item.get("hwnd") or 0)
        win32_items.append({
            "id": f"win32:{idx}",
            "kind": "win32",
            "title": str(item.get("window_name") or "未命名窗口"),
            "subtitle": f"[{hwnd}] {item.get('class_name') or '未知类名'}",
            "enabled": hwnd != 0,
            "tags": [],
        })
    overview["win32"]["items"] = win32_items

    task_views = [item.model_dump() for item in facade.list_task_views()]
    return _ok(
        {
            "systemState": system_state,
            "editorSession": _EDITOR_SESSION,
            "deviceOverview": overview,
            "taskSummary": {
                "count": len(task_views),
                "items": task_views,
            },
            "blocklyFiles": _list_editor_files("blockly"),
            "logChannels": ["default", "runtime.log", "runtime.output"],
        }
    )


@system_router.get("/tasks")
def system_tasks() -> dict[str, Any]:
    facade = get_control_facade()
    items = [item.model_dump() for item in facade.list_task_views()]
    return _ok({"items": items, "count": len(items)})


@system_router.get("/scripts")
def system_scripts() -> dict[str, Any]:
    facade = get_control_facade()
    items = [item.model_dump() for item in facade.list_scripts()]
    return _ok({"items": items, "count": len(items)})


@system_router.get("/scripts/template")
def get_script_template(scriptPath: str = Query(...)) -> dict[str, Any]:
    template_store = get_template_store()
    try:
        meta = template_store.get_template_meta(scriptPath)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="脚本不存在") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"模板解析失败: {exc}") from exc

    if meta is None:
        return _ok(
            {
                "hasTemplate": False,
                "scriptPath": scriptPath,
                "meta": None,
                "savedConfig": None,
                "configPath": "",
            }
        )

    saved_config = template_store.load_saved_config(scriptPath)
    return _ok(
        {
            "hasTemplate": True,
            "scriptPath": scriptPath,
            "meta": meta.model_dump(by_alias=True, exclude_none=True),
            "savedConfig": saved_config.model_dump(),
            "configPath": template_store.get_saved_config_path(scriptPath),
        }
    )


@system_router.get("/tasks/{task_id}")
def system_task_detail(task_id: str) -> dict[str, Any]:
    facade = get_control_facade()
    item = facade.get_task_detail_view(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _ok(item.model_dump())


@system_router.delete("/tasks/{task_id}")
def system_task_remove(task_id: str) -> dict[str, Any]:
    facade = get_control_facade()
    removed = facade.remove_task(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _ok({"taskId": task_id, "removed": True}, message=f"任务已删除: {task_id}")


@system_router.get("/tasks/{task_id}/logs")
def system_task_logs(task_id: str) -> dict[str, Any]:
    facade = get_control_facade()
    item = facade.get_task_logs(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _ok(item.model_dump())


@system_router.get("/tasks/{task_id}/output")
def system_task_output(task_id: str) -> dict[str, Any]:
    facade = get_control_facade()
    item = facade.get_task_output(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _ok(item.model_dump())


@editor_router.get("/session")
def get_editor_session() -> dict[str, Any]:
    return _ok(_EDITOR_SESSION)


@editor_router.put("/session")
def put_editor_session(payload: EditorSessionPayload) -> dict[str, Any]:
    blockly_document = payload.blocklyDocument or {}
    lua_document = payload.luaDocument or {}
    _EDITOR_SESSION["blocklyDocument"].update(
        {
            "xml": str(blockly_document.get("xml") or ""),
            "filename": str(blockly_document.get("filename") or _EDITOR_SESSION["blocklyDocument"].get("filename") or ""),
            "path": str(blockly_document.get("path") or _EDITOR_SESSION["blocklyDocument"].get("path") or ""),
            "dirty": True,
        }
    )
    _EDITOR_SESSION["luaDocument"].update(
        {
            "content": str(lua_document.get("content") or ""),
            "filename": str(lua_document.get("filename") or _EDITOR_SESSION["luaDocument"].get("filename") or ""),
            "path": str(lua_document.get("path") or _EDITOR_SESSION["luaDocument"].get("path") or ""),
            "dirty": True,
        }
    )
    return _ok(_EDITOR_SESSION, message="编辑器会话已同步")


@editor_router.get("/blockly/files")
def list_blockly_editor_files() -> dict[str, Any]:
    return _ok({"items": _list_editor_files("blockly")})


@editor_router.get("/blockly/files/content")
def get_blockly_editor_file(path: str = Query(...)) -> dict[str, Any]:
    data = _read_editor_file(path, kind="blockly")
    _EDITOR_SESSION["blocklyDocument"].update(
        {
            "xml": data["xml"],
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data)


@editor_router.post("/blockly/files")
def create_blockly_editor_file(payload: BlocklyFileCreatePayload) -> dict[str, Any]:
    data = _create_editor_file(payload.path, payload.xml, kind="blockly")
    _EDITOR_SESSION["blocklyDocument"].update(
        {
            "xml": payload.xml,
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data, message="Blockly 文件已创建")


@editor_router.put("/blockly/files/content")
def update_blockly_editor_file(payload: BlocklyFileUpdatePayload) -> dict[str, Any]:
    data = _update_editor_file(payload.path, payload.xml, payload.expectedMtime, kind="blockly")
    _EDITOR_SESSION["blocklyDocument"].update(
        {
            "xml": payload.xml,
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data, message="Blockly 文件已更新")


@editor_router.post("/blockly/files:validate-name")
def validate_blockly_editor_name(payload: ValidateNamePayload) -> dict[str, Any]:
    return _ok(_validate_editor_name(payload.path, kind="blockly"))


@editor_router.get("/lua/files")
def list_lua_editor_files() -> dict[str, Any]:
    return _ok({"items": _list_editor_files("lua")})


@editor_router.get("/lua/files/content")
def get_lua_editor_file(path: str = Query(...)) -> dict[str, Any]:
    data = _read_editor_file(path, kind="lua")
    _EDITOR_SESSION["luaDocument"].update(
        {
            "content": data["content"],
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data)


@editor_router.post("/lua/files")
def create_lua_editor_file(payload: LuaFileCreatePayload) -> dict[str, Any]:
    data = _create_editor_file(payload.path, payload.content, kind="lua")
    _EDITOR_SESSION["luaDocument"].update(
        {
            "content": payload.content,
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data, message="Lua 文件已创建")


@editor_router.put("/lua/files/content")
def update_lua_editor_file(payload: LuaFileUpdatePayload) -> dict[str, Any]:
    data = _update_editor_file(payload.path, payload.content, payload.expectedMtime, kind="lua")
    _EDITOR_SESSION["luaDocument"].update(
        {
            "content": payload.content,
            "filename": data["filename"],
            "path": data["path"],
            "mtime": data["mtime"],
            "dirty": False,
            "saveMode": "update",
        }
    )
    return _ok(data, message="Lua 文件已更新")


@editor_router.post("/lua/files:validate-name")
def validate_lua_editor_name(payload: ValidateNamePayload) -> dict[str, Any]:
    return _ok(_validate_editor_name(payload.path, kind="lua"))


@run_router.post("/lua")
def run_lua_script(payload: RunLuaPayload) -> dict[str, Any]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    target = payload.sessionLabel or overview.connection.label or "LOCAL"
    
    code = payload.luaCode
    script_path = payload.scriptPath or ""
    
    if not code and script_path:
        try:
            code = facade.read_script(script_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取脚本: {e}")
            
    try:
        task_id = facade.run_script(script_path, code, target)
        return _ok({"taskId": task_id, "sessionLabel": target, "scriptPath": script_path}, message=f"任务已启动: {task_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {e}")


@run_router.post("/pipeline")
def run_pipeline_task(payload: RunPipelinePayload) -> dict[str, Any]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    target = payload.sessionLabel or overview.connection.label or "LOCAL"
    project_path = payload.projectPath or ""

    try:
        task_id = facade.run_pipeline(payload.entry, payload.override, target, project_path)
        return _ok(
            {
                "taskId": task_id,
                "entry": payload.entry,
                "sessionLabel": target,
                "projectPath": project_path,
            },
            message=f"流水线已启动: {task_id}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动流水线失败: {e}")


@run_router.post("/lua/template")
def run_template_workflow(payload: RunTemplatePayload) -> dict[str, Any]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    target = overview.connection.label or "LOCAL"
    template_store = get_template_store()

    meta = template_store.get_template_meta(payload.scriptPath)
    if meta is None:
        raise HTTPException(status_code=404, detail="脚本未声明模板元数据")

    workflow_key = payload.workflowKey or meta.entry.flow
    if not workflow_key:
        raise HTTPException(status_code=400, detail="缺少 workflowKey")

    current_saved = template_store.load_saved_config(payload.scriptPath)
    flow_payload = payload.workflow or {}
    next_saved = TemplateSavedConfig.model_validate(
        {
            **current_saved.model_dump(),
            "scriptPath": payload.scriptPath,
            "selectedFlowKey": workflow_key,
            "flows": {
                **current_saved.model_dump().get("flows", {}),
                workflow_key: flow_payload,
            },
        }
    )
    saved_config = template_store.save_saved_config(payload.scriptPath, next_saved)

    try:
        runtime_code = template_store.build_runtime_script(meta, saved_config, flow_key=workflow_key)
        source_code = facade.read_script(payload.scriptPath)
        task_id = facade.run_script(payload.scriptPath, f"{source_code}\n\n{runtime_code}\n", target)
        return _ok(
            {
                "taskId": task_id,
                "scriptPath": payload.scriptPath,
                "workflowKey": workflow_key,
                "savedConfig": saved_config.model_dump(),
                "configPath": template_store.get_saved_config_path(payload.scriptPath),
                "meta": meta.model_dump(by_alias=True, exclude_none=True),
            },
            message=f"模板工作流已启动: {task_id}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动模板工作流失败: {e}")


@run_router.post("/stop")
def stop_all_tasks() -> dict[str, Any]:
    facade = get_control_facade()
    tasks = facade.list_task_views()
    stopped = 0
    for task in tasks:
        if not task.capabilities.can_stop:
            continue
        if task.kind == "script":
            facade.stop_script(task.task_id)
        else:
            facade.stop_pipeline(task.task_id)
        stopped += 1
    return _ok({"stoppedThreads": stopped}, message=f"已停止 {stopped} 个任务")


@logs_router.get("")
def get_structured_logs(
    limit: int = 200,
    channel: str | None = None,
    sessionLabel: str | None = None,
) -> dict[str, Any]:
    items = _build_log_items(limit=limit, channel=channel, session_label=sessionLabel)
    return _ok({"items": items})


@streams_router.get("/logs")
def stream_logs(
    channel: str | None = None,
    sessionLabel: str | None = None,
    replay: int = 50,
) -> StreamingResponse:
    def event(event_name: str, data: Any) -> str:
        return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        snapshot = _build_log_items(limit=max(0, replay), channel=channel, session_label=sessionLabel)
        yield event("snapshot", {"items": snapshot})
        sent = {item.get("formatted") for item in snapshot}
        while True:
            items = _build_log_items(limit=max(50, replay), channel=channel, session_label=sessionLabel)
            latest = [item for item in items if item.get("formatted") not in sent]
            for item in latest:
                sent.add(item.get("formatted"))
                yield event("log", item)
            yield event("heartbeat", {"ts": int(time.time())})
            time.sleep(1.5)

    return StreamingResponse(generate(), media_type="text/event-stream")


def create_web_app(dist_dir: Path) -> FastAPI:
    app = FastAPI(title="MluaScript Web", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(device_router)
    app.include_router(system_router)
    app.include_router(editor_router)
    app.include_router(logs_router)
    app.include_router(streams_router)
    app.include_router(run_router)

    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", response_model=None)
    def index() -> Response:
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(
            {
                "ok": False,
                "message": "未找到 mluascript_web 构建产物，请先在前端目录执行 npm run build",
                "distDir": str(dist_dir),
            },
            status_code=503,
        )

    @app.get("/{full_path:path}", response_model=None)
    def spa_fallback(full_path: str) -> Response:
        target = dist_dir / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(
            {
                "ok": False,
                "message": "未找到 mluascript_web 构建产物，请先在前端目录执行 npm run build",
                "distDir": str(dist_dir),
            },
            status_code=503,
        )

    return app
