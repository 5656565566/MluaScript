from __future__ import annotations

import base64
import binascii
import hashlib
import io
import hmac
import json
import mimetypes
import secrets
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from mluascript.control.facade import get_control_facade
from mluascript.control.workspace import (
    ArtifactService,
    ArtifactServiceError,
    ProjectService,
    ProjectServiceError,
    TemplateSavedConfig,
    TemplateStore,
    WorkspaceManager,
    get_template_store,
)
from mluascript.frontends.web.preferences import WebPreferences, WebPreferenceService
from mluascript.maa.lifecycle.runtime import initialize_maa_runtime
from mluascript.maa.recognition import find_color, find_feature, find_nnd, find_ocr, find_template
from mluascript.shared.config import WebServerConfig, config
from mluascript.shared.logging import get_logs, get_logs_by_channel, get_logs_by_session

auth_router = APIRouter(prefix="/api/auth")
device_router = APIRouter(prefix="/api/device")
editor_router = APIRouter(prefix="/api/editor")
logs_router = APIRouter(prefix="/api/logs")
streams_router = APIRouter(prefix="/api/streams")
system_router = APIRouter(prefix="/api/system")
run_router = APIRouter(prefix="/api/run")
projects_router = APIRouter(prefix="/api/projects")


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
    previousPath: str | None = None


class LuaFileCreatePayload(BaseModel):
    path: str
    content: str = ""


class LuaFileUpdatePayload(BaseModel):
    path: str
    content: str = ""
    expectedMtime: float | None = None
    previousPath: str | None = None


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


class DeviceClickPayload(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class RunLuaPayload(BaseModel):
    sessionLabel: str | None = None
    luaCode: str = ""
    scriptPath: str | None = None


class RunPipelinePayload(BaseModel):
    entry: str
    override: dict[str, Any] | None = None
    sessionLabel: str | None = None
    projectPath: str = ""


class RunArtifactPayload(BaseModel):
    artifactId: str
    sessionLabel: str | None = None
    templateMode: str = ""
    workflowKey: str = ""
    workflow: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


class RunTemplatePayload(BaseModel):
    mode: str = "workflow"
    scriptPath: str
    workflowKey: str = ""
    workflow: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


class ProjectCreatePayload(BaseModel):
    name: str
    packageId: str = ""
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    directory: str = ""
    template: str = "lua-package"


class ProjectUpdatePayload(BaseModel):
    name: str
    packageId: str
    version: str
    author: str = ""
    description: str = ""


class ProjectFileWritePayload(BaseModel):
    path: str
    content: str = ""
    expectedMtime: float | None = None


class ProjectFileCreatePayload(BaseModel):
    path: str
    content: str = ""


class ProjectDirectoryCreatePayload(BaseModel):
    path: str


class ProjectPathRenamePayload(BaseModel):
    path: str
    newName: str


class ProjectPathMovePayload(BaseModel):
    sourcePath: str
    destinationPath: str


class ProjectBuildPayload(BaseModel):
    generatedLua: str | None = None
    generatedFrom: str | None = None
    generatedModules: dict[str, str] | None = None


class ProjectImageRecognitionPayload(BaseModel):
    kind: Literal["ocr", "template", "feature", "color", "nnd"] = "ocr"
    imagePath: str = ""
    imageBase64: str = ""
    templatePath: str = ""
    modelPath: str = ""
    expected: str = ""
    targets: str = ""
    lower: list[list[int]] = Field(default_factory=list)
    upper: list[list[int]] = Field(default_factory=list)
    roi: list[int] | None = None
    threshold: float | None = None


class ProjectDebugPayload(BaseModel):
    mode: Literal["script", "template", "pipeline"] = "script"

    sessionLabel: str = ""
    entryPath: str = ""
    luaCode: str = ""
    sourceOverrides: dict[str, str] = Field(default_factory=dict)
    templateMode: str = ""
    workflowKey: str = ""
    workflow: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)


class ProjectTemplatePreviewPayload(BaseModel):
    """模板预览使用前端当前源码快照，支持 Blockly 尚未落盘的生成 Lua。"""

    entryPath: str = ""
    luaCode: str = ""
    sourceOverrides: dict[str, str] = Field(default_factory=dict)


class LoginPayload(BaseModel):
    username: str = ""
    password: str = ""


def _create_empty_editor_session() -> dict[str, Any]:
    return {
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


_EDITOR_SESSIONS: dict[str, dict[str, Any]] = {}


def _ok(data: Any, message: str = "", meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "message": message,
        "meta": meta or {},
    }


_AUTH_COOKIE_NAME = "mluascript_session"


def _get_web_config() -> WebServerConfig:
    return config.get(WebServerConfig)


def _sign_session(username: str, issued_at: int, nonce: str, secret: str) -> str:
    payload = f"{username}:{issued_at}:{nonce}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_session_token(username: str, issued_at: int, secret: str) -> str:
    nonce = secrets.token_hex(8)
    signature = _sign_session(username, issued_at, nonce, secret)
    raw = f"{username}:{issued_at}:{nonce}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_session_token(token: str, cfg: WebServerConfig) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, issued_at_text, nonce, signature = raw.rsplit(":", 3)
        issued_at = int(issued_at_text)
    except Exception:
        return None

    if username != cfg.username:
        return None
    if time.time() - issued_at > cfg.session_max_age_seconds:
        return None

    expected = _sign_session(username, issued_at, nonce, cfg.session_secret)
    if not hmac.compare_digest(signature, expected):
        return None
    return username


def _get_authenticated_user(request: Request) -> str | None:
    token = request.cookies.get(_AUTH_COOKIE_NAME, "")
    if not token:
        return None
    return _decode_session_token(token, _get_web_config())


def _get_editor_session_key(request: Request) -> str:
    token = request.cookies.get(_AUTH_COOKIE_NAME, "")
    if token:
        return token
    return f"anonymous:{request.client.host if request.client else 'unknown'}"


def _get_editor_session(request: Request) -> dict[str, Any]:
    key = _get_editor_session_key(request)
    session = _EDITOR_SESSIONS.get(key)
    if session is None:
        session = _create_empty_editor_session()
        _EDITOR_SESSIONS[key] = session
    return session


def require_authenticated_user(request: Request) -> str:
    username = _get_authenticated_user(request)
    if username is None:
        raise HTTPException(status_code=401, detail="未登录")
    return username


def _set_auth_cookie(response: JSONResponse, username: str) -> None:
    cfg = _get_web_config()
    token = _encode_session_token(username, int(time.time()), cfg.session_secret)
    response.set_cookie(
        _AUTH_COOKIE_NAME,
        token,
        max_age=cfg.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def _clear_auth_cookie(response: JSONResponse) -> None:
    response.delete_cookie(_AUTH_COOKIE_NAME, httponly=True, samesite="lax")


@auth_router.get("/status")
def auth_status(request: Request) -> dict[str, Any]:
    username = _get_authenticated_user(request)
    return _ok({"authenticated": username is not None, "username": username or ""})


@auth_router.post("/login")
def auth_login(payload: LoginPayload) -> JSONResponse:
    cfg = _get_web_config()
    username_ok = secrets.compare_digest(payload.username, cfg.username)
    password_ok = secrets.compare_digest(payload.password, cfg.password)
    if not username_ok or not password_ok:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    response = JSONResponse(_ok({"authenticated": True, "username": cfg.username}, message="登录成功"))
    _set_auth_cookie(response, cfg.username)
    return response


@auth_router.post("/logout")
def auth_logout(request: Request) -> JSONResponse:
    _EDITOR_SESSIONS.pop(_get_editor_session_key(request), None)
    response = JSONResponse(_ok({"authenticated": False}, message="已退出登录"))
    _clear_auth_cookie(response)
    return response


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


def _save_editor_file(
    path_text: str,
    content: str,
    expected_mtime: float | None,
    *,
    kind: str,
    previous_path: str | None = None,
) -> dict[str, Any]:
    target, relative = _normalize_editor_file_path(path_text, kind=kind)
    source = target
    if previous_path:
        source, _ = _normalize_editor_file_path(previous_path, kind=kind)
    if not source.exists() or not source.is_file():
        # Save is intentionally idempotent: an editor session may outlive a file
        # removed outside the web UI. Recreate it from the in-memory draft.
        if source != target and target.exists():
            raise HTTPException(status_code=409, detail="目标文件已存在")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": relative,
            "filename": target.name,
            "mtime": target.stat().st_mtime,
            "saveMode": "update",
        }
    if expected_mtime is not None:
        current_mtime = source.stat().st_mtime
        if abs(current_mtime - expected_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="文件已发生变化，请刷新后重试")
    if source != target:
        if target.exists():
            raise HTTPException(status_code=409, detail="目标文件已存在")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
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


def _sse_event(event_name: str, data: Any) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _task_logs_signature(item: Any) -> tuple[int, str, str]:
    payload = item.model_dump() if hasattr(item, "model_dump") else {}
    entries = payload.get("items", []) if isinstance(payload, dict) else []
    if not entries:
        return (0, "", "")
    last = entries[-1] if isinstance(entries[-1], dict) else {}
    return (
        len(entries),
        str(last.get("level") or ""),
        str(last.get("message") or ""),
    )



def _serialize_device_page_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return items



def _build_device_items_payload() -> list[dict[str, Any]]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    buckets = [overview.adb.items, overview.emulator.items, overview.browser.items]
    items: list[dict[str, Any]] = []
    for bucket in buckets:
        for item in bucket:
            items.append(item.model_dump())
    # The overview is paged for the legacy device page UI. The WebUI fetches all
    # discoverable desktop windows in one response, so use the raw discovery list here.
    for index, window in enumerate(facade.device_facade._desktop_raw):
        handle = int(window.get("handle") or window.get("hwnd") or 0)
        backend = str(window.get("platform") or "desktop")
        window_name = str(window.get("window_name") or "未命名窗口")
        class_name = str(window.get("class_name") or "未知类名")
        items.append({
            "id": f"desktop:{index}",
            "kind": "desktop",
            "title": window_name,
            "subtitle": f"[{backend}:{handle}] {class_name}",
            "handle": handle,
            "hwnd": handle,
            "window_name": window_name,
            "class_name": class_name,
            "enabled": handle != 0 or backend == "wlroots",
            "tags": [],
        })
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
    elif kind == "desktop":
        result = facade.find_desktop_windows()
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


def _preferences_for_request(request: Request) -> WebPreferences:
    username = _get_authenticated_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    return _preference_service(request).get(username)


@system_router.get("/preferences")
def get_web_preferences(request: Request) -> dict[str, Any]:
    return _ok(_preferences_for_request(request).model_dump(by_alias=True))


@system_router.put("/preferences")
def put_web_preferences(payload: WebPreferences, request: Request) -> dict[str, Any]:
    username = _get_authenticated_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    saved = _preference_service(request).put(username, payload)
    return _ok(saved.model_dump(by_alias=True), message="Web 偏好设置已保存")


@system_router.get("/bootstrap")
def system_bootstrap(request: Request) -> dict[str, Any]:
    facade = get_control_facade()
    system_state = facade.get_system_state().model_dump()
    overview = facade.get_device_overview().model_dump()
    editor_session = _get_editor_session(request)

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
    
    desktop_items = []
    for idx, item in enumerate(facade.device_facade._desktop_raw):
        handle = int(item.get("handle") or item.get("hwnd") or 0)
        backend = str(item.get("platform") or "desktop")
        desktop_items.append({
            "id": f"desktop:{idx}",
            "kind": "desktop",
            "title": str(item.get("window_name") or "未命名窗口"),
            "subtitle": f"[{backend}:{handle}] {item.get('class_name') or '未知类名'}",
            "enabled": handle != 0 or backend == "wlroots",
            "tags": [],
        })
    overview["desktop"]["items"] = desktop_items

    task_views = [item.model_dump() for item in facade.list_task_views()]
    return _ok(
        {
            "systemState": system_state,
            "editorSession": editor_session,
            "deviceOverview": overview,
            "taskSummary": {
                "count": len(task_views),
                "items": task_views,
            },
            "blocklyFiles": _list_editor_files("blockly"),
            "logChannels": ["default", "runtime.log", "runtime.output"],
            "preferences": _preferences_for_request(request).model_dump(by_alias=True),
        }
    )


@system_router.get("/tasks")
def system_tasks() -> dict[str, Any]:
    facade = get_control_facade()
    items = [item.model_dump() for item in facade.list_task_views()]
    return _ok({"items": items, "count": len(items)})


@system_router.get("/scripts")
def system_scripts(request: Request) -> dict[str, Any]:
    items = [item.model_dump() for item in _artifact_service(request).list_artifacts()]
    return _ok({"items": items, "count": len(items)})


@system_router.get("/scripts/{artifact_id}/readme")
def system_script_readme(artifact_id: str, request: Request) -> dict[str, Any]:
    try:
        readme = _artifact_service(request).read_readme(artifact_id)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok(readme.model_dump())


@system_router.get("/scripts/{artifact_id}/template")
def system_script_template(artifact_id: str, request: Request) -> dict[str, Any]:
    """读取构建包当前入口的唯一模板配置，不修改归档内容。"""

    service = _artifact_service(request)
    try:
        source = service.get_template_source(artifact_id)
        store = TemplateStore(
            WorkspaceManager(service.builds_root.parent.parent),
            config_dir=service.template_config_dir(artifact_id),
        )
        meta = store.get_template_meta_from_source(source.code, script_path=source.script_path)
        if meta is None:
            return _ok({"hasTemplate": False, "scriptPath": source.script_path, "meta": None, "savedConfig": None})
        saved_config = store.load_saved_config(source.script_path)
        readme = service.read_readme(artifact_id) if source.artifact.has_readme else None
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"模板解析失败: {exc}") from exc
    return _ok(
        {
            "hasTemplate": True,
            "scriptPath": source.script_path,
            "meta": meta.model_dump(by_alias=True, exclude_none=True),
            "savedConfig": saved_config.model_dump(),
            "configPath": store.get_saved_config_path(source.script_path),
            "readme": readme.model_dump() if readme else None,
            "artifactId": source.artifact.id,
            "name": source.artifact.name,
        }
    )


@device_router.post("/click")
def click_device(payload: DeviceClickPayload) -> dict[str, Any]:
    result = get_control_facade().click_current_device(payload.x, payload.y)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message or "点击设备失败")
    return _ok({"message": result.message}, message=result.message)


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
    try:
        readme = template_store.get_readme(scriptPath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(
        {
            "hasTemplate": True,
            "scriptPath": scriptPath,
            "meta": meta.model_dump(by_alias=True, exclude_none=True),
            "savedConfig": saved_config.model_dump(),
            "configPath": template_store.get_saved_config_path(scriptPath),
            "readme": readme,
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
def get_editor_session(request: Request) -> dict[str, Any]:
    return _ok(_get_editor_session(request))


@editor_router.put("/session")
def put_editor_session(payload: EditorSessionPayload, request: Request) -> dict[str, Any]:
    editor_session = _get_editor_session(request)
    blockly_document = payload.blocklyDocument or {}
    lua_document = payload.luaDocument or {}
    editor_session["blocklyDocument"].update(
        {
            "xml": str(blockly_document.get("xml") or ""),
            "filename": str(blockly_document.get("filename") or editor_session["blocklyDocument"].get("filename") or ""),
            "path": str(blockly_document.get("path") or editor_session["blocklyDocument"].get("path") or ""),
            "mtime": blockly_document.get("mtime", editor_session["blocklyDocument"].get("mtime")),
            "saveMode": str(blockly_document.get("saveMode") or editor_session["blocklyDocument"].get("saveMode") or "create"),
            "dirty": bool(blockly_document.get("dirty", True)),
        }
    )
    editor_session["luaDocument"].update(
        {
            "content": str(lua_document.get("content") or ""),
            "filename": str(lua_document.get("filename") or editor_session["luaDocument"].get("filename") or ""),
            "path": str(lua_document.get("path") or editor_session["luaDocument"].get("path") or ""),
            "mtime": lua_document.get("mtime", editor_session["luaDocument"].get("mtime")),
            "saveMode": str(lua_document.get("saveMode") or editor_session["luaDocument"].get("saveMode") or "create"),
            "dirty": bool(lua_document.get("dirty", True)),
        }
    )
    return _ok(editor_session, message="编辑器会话已同步")


@editor_router.get("/blockly/files")
def list_blockly_editor_files() -> dict[str, Any]:
    return _ok({"items": _list_editor_files("blockly")})


@editor_router.get("/blockly/files/content")
def get_blockly_editor_file(request: Request, path: str = Query(...)) -> dict[str, Any]:
    data = _read_editor_file(path, kind="blockly")
    editor_session = _get_editor_session(request)
    editor_session["blocklyDocument"].update(
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
def create_blockly_editor_file(payload: BlocklyFileCreatePayload, request: Request) -> dict[str, Any]:
    data = _create_editor_file(payload.path, payload.xml, kind="blockly")
    editor_session = _get_editor_session(request)
    editor_session["blocklyDocument"].update(
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
def update_blockly_editor_file(payload: BlocklyFileUpdatePayload, request: Request) -> dict[str, Any]:
    data = _save_editor_file(
        payload.path,
        payload.xml,
        payload.expectedMtime,
        kind="blockly",
        previous_path=payload.previousPath,
    )
    editor_session = _get_editor_session(request)
    editor_session["blocklyDocument"].update(
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
def get_lua_editor_file(request: Request, path: str = Query(...)) -> dict[str, Any]:
    data = _read_editor_file(path, kind="lua")
    editor_session = _get_editor_session(request)
    editor_session["luaDocument"].update(
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
def create_lua_editor_file(payload: LuaFileCreatePayload, request: Request) -> dict[str, Any]:
    data = _create_editor_file(payload.path, payload.content, kind="lua")
    editor_session = _get_editor_session(request)
    editor_session["luaDocument"].update(
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
def update_lua_editor_file(payload: LuaFileUpdatePayload, request: Request) -> dict[str, Any]:
    data = _save_editor_file(
        payload.path,
        payload.content,
        payload.expectedMtime,
        kind="lua",
        previous_path=payload.previousPath,
    )
    editor_session = _get_editor_session(request)
    editor_session["luaDocument"].update(
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


def _project_service(request: Request) -> ProjectService:
    return request.app.state.project_service


def _artifact_service(request: Request) -> ArtifactService:
    service = getattr(request.app.state, "artifact_service", None)
    if not isinstance(service, ArtifactService):
        raise HTTPException(status_code=503, detail="构建产物服务不可用")
    return service


def _preference_service(request: Request) -> WebPreferenceService:
    service = getattr(request.app.state, "preference_service", None)
    if not isinstance(service, WebPreferenceService):
        raise HTTPException(status_code=503, detail="Web 偏好设置服务不可用")
    return service


def _project_error(exc: ProjectServiceError) -> HTTPException:
    detail = exc.args[0] if exc.args else str(exc)
    if isinstance(detail, dict):
        return HTTPException(status_code=400, detail=detail)
    return HTTPException(status_code=400, detail=str(detail))


def _project_template_store(service: ProjectService, project_key: str, project_root: str) -> TemplateStore:
    """为项目模板使用项目内源码和 Web 私有配置目录。"""

    return TemplateStore(
        WorkspaceManager(Path(project_root)),
        config_dir=service.get_template_config_root(project_key),
    )


@projects_router.get("")
def list_projects(request: Request) -> dict[str, Any]:
    return _ok({"items": [item.model_dump() for item in _project_service(request).list_projects()]})


@projects_router.post("")
def create_project(payload: ProjectCreatePayload, request: Request) -> dict[str, Any]:
    try:
        project = _project_service(request).create_project(
            name=payload.name,
            package_id=payload.packageId,
            version=payload.version,
            author=payload.author,
            description=payload.description,
            directory=payload.directory,
            template=payload.template,
        )
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    return _ok(project.model_dump(), message="项目已创建")


@projects_router.patch("/{project_key}")
def update_project(project_key: str, payload: ProjectUpdatePayload, request: Request) -> dict[str, Any]:
    try:
        project = _project_service(request).update_project(
            project_key,
            name=payload.name,
            package_id=payload.packageId,
            version=payload.version,
            author=payload.author,
            description=payload.description,
        )
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    return _ok(project.model_dump(), message="项目信息已更新")


@projects_router.post("/{project_key}:open")
def open_project(project_key: str, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).open_project(project_key)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok(data, message="项目已打开")


@projects_router.get("/{project_key}/tree")
def list_project_tree(project_key: str, request: Request) -> dict[str, Any]:
    try:
        items = _project_service(request).list_tree(project_key)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"items": [item.model_dump() for item in items]})


@projects_router.get("/{project_key}/modules")
def list_project_modules(project_key: str, request: Request) -> dict[str, Any]:
    try:
        modules = _project_service(request).get_module_index(project_key)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"modules": modules})


@projects_router.get("/{project_key}/template")
def get_project_template(project_key: str, request: Request, path: str = Query(...)) -> dict[str, Any]:
    """按受控项目路径读取模板元数据，避免前端拼接宿主机绝对路径。"""

    try:
        target = _project_service(request).prepare_debug_target(project_key, entry_path=path)
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    template_store = _project_template_store(_project_service(request), project_key, target.project_root)
    try:
        meta = template_store.get_template_meta(target.entry_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="脚本不存在") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"模板解析失败: {exc}") from exc
    if meta is None:
        return _ok({"hasTemplate": False, "scriptPath": target.entry_path, "meta": None, "savedConfig": None})
    saved_config = template_store.load_saved_config(target.entry_path)
    try:
        readme = template_store.get_readme(target.entry_path)
    except ValueError as exc:
        raise _project_error(ProjectServiceError(str(exc))) from exc
    return _ok(
        {
            "hasTemplate": True,
            "scriptPath": target.entry_path,
            "meta": meta.model_dump(by_alias=True, exclude_none=True),
            "savedConfig": saved_config.model_dump(),
            "configPath": template_store.get_saved_config_path(target.entry_path),
            "readme": readme,
        }
    )


@projects_router.post("/{project_key}/template:preview")
def preview_project_template(
    project_key: str,
    payload: ProjectTemplatePreviewPayload,
    request: Request,
) -> dict[str, Any]:
    """解析当前项目入口的内存 Lua 快照，不要求生成文件真实存在。"""

    service = _project_service(request)
    try:
        target = service.prepare_debug_target(
            project_key,
            entry_path=payload.entryPath,
            source_overrides=payload.sourceOverrides,
        )
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    template_store = _project_template_store(service, project_key, target.project_root)
    try:
        meta = template_store.get_template_meta_from_source(payload.luaCode, script_path=target.entry_path)
        if meta is None:
            return _ok({"hasTemplate": False, "scriptPath": target.entry_path, "meta": None, "savedConfig": None})
        saved_config = template_store.load_saved_config(target.entry_path)
        readme = template_store.get_readme(target.entry_path)
    except ValueError as exc:
        raise _project_error(ProjectServiceError(str(exc))) from exc
    return _ok(
        {
            "hasTemplate": True,
            "scriptPath": target.entry_path,
            "meta": meta.model_dump(by_alias=True, exclude_none=True),
            "savedConfig": saved_config.model_dump(),
            "configPath": template_store.get_saved_config_path(target.entry_path),
            "readme": readme,
        }
    )


@projects_router.get("/{project_key}/files/content")
def read_project_file(project_key: str, request: Request, path: str = Query(...)) -> dict[str, Any]:
    try:
        data = _project_service(request).read_file(project_key, path)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(data.model_dump(by_alias=True))


@projects_router.put("/{project_key}/files/content")
def write_project_file(project_key: str, payload: ProjectFileWritePayload, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).write_file(
            project_key,
            payload.path,
            payload.content,
            payload.expectedMtime,
        )
    except ProjectServiceError as exc:
        status_code = 409 if "发生变化" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return _ok(data.model_dump(by_alias=True), message="项目文件已保存")


@projects_router.post("/{project_key}/files")
def create_project_file(project_key: str, payload: ProjectFileCreatePayload, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).create_file(project_key, payload.path, payload.content)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(data.model_dump(by_alias=True), message="项目文件已创建")


@projects_router.delete("/{project_key}/files")
def delete_project_file(project_key: str, request: Request, path: str = Query(...)) -> dict[str, Any]:
    try:
        deleted_path = _project_service(request).delete_file(project_key, path)
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    return _ok({"path": deleted_path}, message="项目文件已删除")


@projects_router.post("/{project_key}/directories")
def create_project_directory(project_key: str, payload: ProjectDirectoryCreatePayload, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).create_directory(project_key, payload.path)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(data.model_dump(), message="项目目录已创建")


@projects_router.patch("/{project_key}/tree")
def rename_project_path(project_key: str, payload: ProjectPathRenamePayload, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).rename_path(project_key, payload.path, payload.newName)
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    return _ok(data.model_dump(), message="项目路径已重命名")


@projects_router.patch("/{project_key}/tree:move")
def move_project_path(project_key: str, payload: ProjectPathMovePayload, request: Request) -> dict[str, Any]:
    try:
        data = _project_service(request).move_path(project_key, payload.sourcePath, payload.destinationPath)
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    return _ok(data.model_dump(), message="项目路径已移动")


@projects_router.put("/{project_key}/files/binary")
async def upload_project_file(
    project_key: str,
    request: Request,
    path: str = Query(...),
    overwrite: bool = Query(False),
) -> dict[str, Any]:
    service = _project_service(request)
    try:
        # 原始请求体按块写入临时文件，避免模型和资源文件经过 Base64 或整块驻留内存。
        with service.open_binary_writer(project_key, path, overwrite=overwrite) as (stream, normalized):
            async for chunk in request.stream():
                if chunk:
                    stream.write(chunk)
        data = service.get_tree_item(project_key, normalized)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(data.model_dump(), message="项目文件已上传")


@projects_router.get("/{project_key}/files/raw")
def download_project_file(project_key: str, request: Request, path: str = Query(...)) -> FileResponse:
    try:
        target, normalized = _project_service(request).get_file_path(project_key, path)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    content_disposition_type = "inline" if media_type.startswith("image/") else "attachment"
    return FileResponse(
        target,
        media_type=media_type,
        filename=Path(normalized).name,
        content_disposition_type=content_disposition_type,
    )


@projects_router.post("/{project_key}/validate")
def validate_project(project_key: str, request: Request) -> dict[str, Any]:
    try:
        diagnostics = _project_service(request).validate(project_key)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok(
        {
            "valid": not any(item.severity == "error" for item in diagnostics),
            "diagnostics": [item.model_dump() for item in diagnostics],
        }
    )


@projects_router.post("/{project_key}/build")
def build_project(project_key: str, payload: ProjectBuildPayload, request: Request) -> dict[str, Any]:
    try:
        result = _project_service(request).build(
            project_key,
            generated_lua=payload.generatedLua,
            generated_from=payload.generatedFrom,
            generated_modules=payload.generatedModules,
        )
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    data = result.model_dump(exclude={"artifact_path"})
    data["downloadPath"] = f"/api/projects/{project_key}/builds/{result.build_id}/download"
    return _ok(data, message="项目已打包")


@projects_router.post("/{project_key}/debug")
def debug_project(project_key: str, payload: ProjectDebugPayload, request: Request) -> dict[str, Any]:
    """直接执行项目源码快照；不创建包，也不把 Blockly 生成文件写回项目。"""

    facade = get_control_facade()
    overview = facade.get_device_overview()
    session_label = payload.sessionLabel or overview.connection.label or "LOCAL"
    service = _project_service(request)
    if payload.mode == "pipeline":
        try:
            target = service.prepare_pipeline_debug_target(project_key, descriptor_path=payload.entryPath)
            task_id = facade.run_pipeline(target.entry, target.override, session_label, target.project_path)
        except ProjectServiceError as exc:
            raise _project_error(exc) from exc
        return _ok(
            {
                "taskId": task_id,
                "kind": "pipeline",
                "projectKey": project_key,
                "entryPath": target.descriptor_path,
            },
            message=f"调试任务已启动: {task_id}",
        )

    try:
        target = service.prepare_debug_target(
            project_key,
            entry_path=payload.entryPath,
            source_overrides=payload.sourceOverrides,
        )
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc

    code = payload.luaCode
    if payload.mode == "template":
        template_store = _project_template_store(service, project_key, target.project_root)
        try:
            meta = template_store.get_template_meta_from_source(code, script_path=target.entry_path)
            if meta is None:
                raise ProjectServiceError("当前脚本没有模板元数据")
            current_saved = template_store.load_saved_config(target.entry_path)
            if payload.templateMode == "task" or (meta.mode == "task" and not meta.flows):
                task_key = str(payload.runtime.get("selectedTaskKey") or meta.entry.task or "").strip()
                tasks = {
                    str(key): {"params": value if isinstance(value, dict) else {}}
                    for key, value in (payload.runtime.get("tasks") or {}).items()
                }
                saved = template_store.save_saved_config(
                    target.entry_path,
                    TemplateSavedConfig.model_validate({
                        **current_saved.model_dump(),
                        "scriptPath": target.entry_path,
                        "selectedTaskKey": task_key,
                        "tasks": tasks,
                    }),
                )
                runtime_code = template_store.build_task_runtime_script(meta, saved, task_key=task_key)
            else:
                workflow_key = payload.workflowKey or meta.entry.flow
                if not workflow_key:
                    raise ProjectServiceError("模板调试缺少工作流入口")
                saved = template_store.save_saved_config(
                    target.entry_path,
                    TemplateSavedConfig.model_validate({
                        **current_saved.model_dump(),
                        "scriptPath": target.entry_path,
                        "selectedFlowKey": workflow_key,
                        "flows": {
                            **current_saved.model_dump().get("flows", {}),
                            workflow_key: payload.workflow,
                        },
                    }),
                )
                runtime_code = template_store.build_runtime_script(meta, saved, flow_key=workflow_key)
            code = f"{code}\n\n{runtime_code}\n"
        except (KeyError, ProjectServiceError, ValueError) as exc:
            raise _project_error(ProjectServiceError(str(exc))) from exc

    try:
        task_id = facade.run_script(
            target.script_path,
            code,
            session_label,
            source_overrides=target.source_overrides,
            summary={
                "debug": True,
                "project_key": project_key,
                "entry_path": target.entry_path,
                "debug_mode": payload.mode,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动项目调试失败: {exc}") from exc
    return _ok(
        {
            "taskId": task_id,
            "kind": "script",
            "projectKey": project_key,
            "entryPath": target.entry_path,
        },
        message=f"调试任务已启动: {task_id}",
    )


def _recognition_image_array(service: ProjectService, project_key: str, payload: ProjectImageRecognitionPayload) -> np.ndarray:
    try:
        if payload.imageBase64:
            encoded = payload.imageBase64.split(",", 1)[-1]
            raw = base64.b64decode(encoded, validate=True)
        elif payload.imagePath:
            target = Path(_recognition_resource_path(service, project_key, payload.imagePath, "测试图片"))
            raw = target.read_bytes()
        else:
            raise ProjectServiceError("请选择识图测试图片")
        with Image.open(io.BytesIO(raw)) as image:
            rgb = np.asarray(image.convert("RGB"))
        return rgb[:, :, ::-1].copy()
    except (OSError, ValueError, binascii.Error) as exc:
        raise ProjectServiceError(f"测试图片无效: {exc}") from exc


def _recognition_resource_path(service: ProjectService, project_key: str, relative_path: str, label: str) -> str:
    reference = str(relative_path or "").strip().replace("\\", "/")
    if not reference:
        raise ProjectServiceError(f"请选择{label}")
    resolved_path = reference
    if ":" in reference:
        resource_key, resource_relative = reference.split(":", 1)
        manifest = service.open_project(project_key).get("manifest") or {}
        resource_root = str((manifest.get("resources") or {}).get(resource_key) or "").strip().replace("\\", "/")
        if not resource_root:
            raise ProjectServiceError(f"资源目录不存在: {resource_key}")
        if not resource_relative.strip("/"):
            raise ProjectServiceError(f"{label}资源路径不能为空")
        resolved_path = f"{resource_root.rstrip('/')}/{resource_relative.lstrip('/')}"
    target, _ = service.get_file_path(project_key, resolved_path)
    return str(target)


@projects_router.post("/{project_key}/recognize-image")
def recognize_project_image(
    project_key: str,
    payload: ProjectImageRecognitionPayload,
    request: Request,
) -> dict[str, Any]:
    service = _project_service(request)
    try:
        image = _recognition_image_array(service, project_key, payload)
        facade = get_control_facade()
        context = facade.device_facade._maa_facade.context
        initialize_maa_runtime(context)
        if context.tasker is None:
            raise ProjectServiceError("Maa 识别运行时未初始化")

        entry = f"WebImageDebug:{payload.kind}"
        if payload.kind == "ocr":
            expected = [item.strip() for item in payload.expected.split("|") if item.strip()] or None
            result = find_ocr(context, entry, expected=expected, roi=payload.roi, image=image)
        elif payload.kind == "template":
            template = _recognition_resource_path(service, project_key, payload.templatePath, "模板图片")
            result = find_template(
                context,
                entry,
                template=template,
                roi=payload.roi,
                threshold=payload.threshold,
                image=image,
            )
        elif payload.kind == "feature":
            template = _recognition_resource_path(service, project_key, payload.templatePath, "模板图片")
            result = find_feature(context, entry, template=template, roi=payload.roi, image=image)
        elif payload.kind == "color":
            result = find_color(context, entry, lower=payload.lower, upper=payload.upper, roi=payload.roi, image=image)
        else:
            model = _recognition_resource_path(service, project_key, payload.modelPath, "检测模型")
            targets = [item.strip() for item in payload.targets.split("|") if item.strip()] or None
            result = find_nnd(context, entry, model=model, targets=targets, roi=payload.roi, image=image)
    except ProjectServiceError as exc:
        raise _project_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"识图调试失败: {exc}") from exc

    normalized = result or {"hit": False, "entry": f"WebImageDebug:{payload.kind}"}
    return _ok({"result": normalized, "message": "识图完成"}, message="识图完成")


@projects_router.get("/{project_key}/builds/{build_id}/download")
def download_project_build(project_key: str, build_id: str, request: Request) -> FileResponse:
    try:
        artifact, filename = _project_service(request).get_build_artifact(project_key, build_id)
    except ProjectServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(artifact, media_type="application/octet-stream", filename=filename)


def _editor_script_run_path(raw_path: str | None) -> str:
    """把编辑器内的相对路径转换为工作区脚本路径。"""
    if raw_path and str(raw_path).strip():
        target, _ = _normalize_editor_file_path(str(raw_path), kind="lua")
    else:
        # 仅作为内存代码的运行目录定位，不会在磁盘创建该文件。
        target = (_editor_lua_root() / "untitled.lua").resolve()
    return target.relative_to(Path.cwd().resolve()).as_posix()


@run_router.post("/lua")
def run_lua_script(payload: RunLuaPayload) -> dict[str, Any]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    target = payload.sessionLabel or overview.connection.label or "LOCAL"
    
    code = payload.luaCode
    script_path = _editor_script_run_path(payload.scriptPath)
    
    if not code and payload.scriptPath:
        try:
            code = facade.read_script(script_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取脚本: {e}")
            
    try:
        task_id = facade.run_script(script_path, code, target)
        return _ok({"taskId": task_id, "sessionLabel": target, "scriptPath": script_path}, message=f"任务已启动: {task_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {e}")


@run_router.post("/artifact")
def run_build_artifact(payload: RunArtifactPayload, request: Request) -> dict[str, Any]:
    facade = get_control_facade()
    overview = facade.get_device_overview()
    target = payload.sessionLabel or overview.connection.label or "LOCAL"
    try:
        prepared = _artifact_service(request).prepare_run(payload.artifactId)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if prepared.mode == "script":
            if payload.templateMode:
                artifact_service = _artifact_service(request)
                template_script_path = Path(prepared.script_path).name
                if prepared.project_path:
                    try:
                        template_script_path = Path(prepared.script_path).resolve().relative_to(
                            Path(prepared.project_path).resolve()
                        ).as_posix()
                    except ValueError as exc:
                        raise ArtifactServiceError("构建包入口路径无效") from exc
                store = TemplateStore(
                    WorkspaceManager(Path(prepared.project_path or Path(prepared.script_path).parent)),
                    config_dir=artifact_service.template_config_dir(payload.artifactId),
                )
                meta = store.get_template_meta_from_source(prepared.code, script_path=template_script_path)
                if meta is None:
                    raise ArtifactServiceError("构建入口没有模板元数据")
                current_saved = store.load_saved_config(template_script_path)
                if payload.templateMode == "task" or (meta.mode == "task" and not meta.flows):
                    task_key = str(payload.runtime.get("selectedTaskKey") or meta.entry.task or "").strip()
                    tasks = {
                        str(key): {"params": value if isinstance(value, dict) else {}}
                        for key, value in (payload.runtime.get("tasks") or {}).items()
                    }
                    saved = store.save_saved_config(
                        template_script_path,
                        TemplateSavedConfig.model_validate({
                            **current_saved.model_dump(),
                            "scriptPath": template_script_path,
                            "selectedTaskKey": task_key,
                            "tasks": tasks,
                        }),
                    )
                    runtime_code = store.build_task_runtime_script(meta, saved, task_key=task_key)
                else:
                    workflow_key = payload.workflowKey or meta.entry.flow
                    if not workflow_key:
                        raise ArtifactServiceError("模板调试缺少工作流入口")
                    saved = store.save_saved_config(
                        template_script_path,
                        TemplateSavedConfig.model_validate({
                            **current_saved.model_dump(),
                            "scriptPath": template_script_path,
                            "selectedFlowKey": workflow_key,
                            "flows": {
                                **current_saved.model_dump().get("flows", {}),
                                workflow_key: payload.workflow,
                            },
                        }),
                    )
                    runtime_code = store.build_runtime_script(meta, saved, flow_key=workflow_key)
                prepared.code = f"{prepared.code}\n\n{runtime_code}\n"
            task_id = facade.run_script(
                prepared.script_path,
                prepared.code,
                target,
                title=prepared.artifact.path,
                summary=prepared.summary,
                cleanup_dir=prepared.cleanup_dir,
            )
        else:
            task_id = facade.run_pipeline(
                prepared.entry,
                prepared.override,
                target,
                prepared.project_path,
                title=prepared.artifact.path,
                cleanup_dir=prepared.cleanup_dir,
            )
    except ArtifactServiceError as exc:
        prepared.cleanup()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        prepared.cleanup()
        raise HTTPException(status_code=500, detail=f"启动构建产物失败: {exc}") from exc

    return _ok(
        {
            "taskId": task_id,
            "kind": "script" if prepared.mode == "script" else "pipeline",
            "artifactId": prepared.artifact.id,
            "name": prepared.artifact.name,
            "sessionLabel": target,
        },
        message=f"构建产物已启动: {task_id}",
    )


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


def _stop_task(task_id: str, expected_kind: str) -> dict[str, Any]:
    facade = get_control_facade()
    task = facade.get_task_detail_view(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在或已删除: {task_id}")
    if task.kind != expected_kind:
        raise HTTPException(status_code=409, detail=f"任务类型不匹配: {task.kind}")
    if task.status == "stopped":
        return _ok({"taskId": task_id, "status": task.status}, message=f"任务已经停止: {task_id}")
    if not task.capabilities.can_stop:
        raise HTTPException(status_code=409, detail=f"任务当前状态不可停止: {task.status}")

    if expected_kind == "script":
        facade.stop_script(task_id)
    else:
        facade.stop_pipeline(task_id)

    updated = facade.get_task_detail_view(task_id)
    status = updated.status if updated is not None else "stopped"
    return _ok({"taskId": task_id, "status": status}, message=f"已停止任务: {task_id}")


@run_router.post("/script/{task_id}/stop")
def stop_script_task(task_id: str) -> dict[str, Any]:
    return _stop_task(task_id, "script")


@run_router.post("/pipeline/{task_id}/stop")
def stop_pipeline_task(task_id: str) -> dict[str, Any]:
    return _stop_task(task_id, "pipeline")


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
    def generate():
        snapshot = _build_log_items(limit=max(0, replay), channel=channel, session_label=sessionLabel)
        yield _sse_event("snapshot", {"items": snapshot})
        sent = {item.get("formatted") for item in snapshot}
        while True:
            items = _build_log_items(limit=max(50, replay), channel=channel, session_label=sessionLabel)
            latest = [item for item in items if item.get("formatted") not in sent]
            for item in latest:
                sent.add(item.get("formatted"))
                yield _sse_event("log", item)
            yield _sse_event("heartbeat", {"ts": int(time.time())})
            time.sleep(1.5)

    return StreamingResponse(generate(), media_type="text/event-stream")


@streams_router.get("/tasks/{task_id}/logs")
def stream_task_logs(task_id: str) -> StreamingResponse:
    facade = get_control_facade()

    def generate():
        current = facade.get_task_logs(task_id)
        if current is None:
            yield _sse_event("not_found", {"taskId": task_id})
            return
        yield _sse_event("snapshot", current.model_dump())
        signature = _task_logs_signature(current)
        while True:
            latest = facade.get_task_logs(task_id)
            if latest is None:
                yield _sse_event("not_found", {"taskId": task_id})
                return
            next_signature = _task_logs_signature(latest)
            if next_signature != signature:
                signature = next_signature
                yield _sse_event("update", latest.model_dump())
            yield _sse_event("heartbeat", {"ts": int(time.time())})
            time.sleep(1.0)

    return StreamingResponse(generate(), media_type="text/event-stream")


@streams_router.get("/tasks/{task_id}/output")
def stream_task_output(task_id: str) -> StreamingResponse:
    facade = get_control_facade()

    def generate():
        current = facade.get_task_output(task_id)
        if current is None:
            yield _sse_event("not_found", {"taskId": task_id})
            return
        yield _sse_event("snapshot", current.model_dump())
        version = current.version
        while True:
            latest = facade.get_task_output(task_id)
            if latest is None:
                yield _sse_event("not_found", {"taskId": task_id})
                return
            if latest.version != version:
                version = latest.version
                yield _sse_event("update", latest.model_dump())
            yield _sse_event("heartbeat", {"ts": int(time.time())})
            time.sleep(0.75)

    return StreamingResponse(generate(), media_type="text/event-stream")


def create_web_app(dist_dir: Path, *, preferences_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="MluaScript Web", version="1.0.0")
    try:
        configured_roots = list(getattr(_get_web_config(), "project_roots", []) or [])
    except Exception:
        configured_roots = []
    if not configured_roots:
        configured_roots = [str(Path.cwd() / ".mluascript_web" / "projects")]
    primary_project_root = Path(configured_roots[0]).expanduser().resolve()
    artifact_root = primary_project_root.parent / "builds"
    app.state.project_service = ProjectService(
        configured_roots,
        artifact_root=artifact_root,
    )
    app.state.artifact_service = ArtifactService(
        artifact_root,
        runtime_root=primary_project_root.parent / "runtime" / "tasks",
        project_service=app.state.project_service,
    )
    app.state.preference_service = WebPreferenceService(
        preferences_path or (Path.cwd() / ".mluascript_web" / "settings" / "web" / "preferences.json")
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    protected_dependencies = [Depends(require_authenticated_user)]
    app.include_router(device_router, dependencies=protected_dependencies)
    app.include_router(system_router, dependencies=protected_dependencies)
    app.include_router(editor_router, dependencies=protected_dependencies)
    app.include_router(projects_router, dependencies=protected_dependencies)
    app.include_router(logs_router, dependencies=protected_dependencies)
    app.include_router(streams_router, dependencies=protected_dependencies)
    app.include_router(run_router, dependencies=protected_dependencies)

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
