from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast
from unittest.mock import MagicMock

from mluascript.control.facade import ControlFacade
from mluascript.control.integration.facade import IntegrationFacade
from mluascript.control.integration.models import MaaPipelineRunContext, RunStatus, ScriptRunContext
from mluascript.control.state.manager import StateManager
from mluascript.control.workspace.manager import WorkspaceManager
from mluascript.control.workspace.models import PipelineRunLocator, ScriptAsset, ScriptInfo, ScriptRunLocator, WorkspaceProject
from mluascript.maa.config import MaaDeviceConfig
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths
from mluascript.runtime.output_buffer import TaskOutputBuffer
from mluascript.runtime.exception import LuaExitException
from mluascript.runtime.stopper import Stopper
from mluascript.runtime.threading.manager import RuntimeThreadManager
from mluascript.runtime.threading.task import RuntimeTask


class FakeRuntime:
    def __init__(self, *, result: Any = None, error: Exception | None = None, wait_for_cancel: bool = False) -> None:
        self.result = result
        self.error = error
        self.wait_for_cancel = wait_for_cancel
        self.stopper: Stopper | None = None

    def execute(self, file_content: str) -> Any:
        if self.wait_for_cancel:
            assert self.stopper is not None
            while not self.stopper.is_stop_requested:
                pass
            raise LuaExitException("stopped")
        if self.error is not None:
            raise self.error
        return self.result


class FakeTaskJob:
    def __init__(self, succeeded: bool = True, detail: Any = None) -> None:
        self.succeeded = succeeded
        self._detail = detail
        self.wait_called = False

    def wait(self) -> "FakeTaskJob":
        self.wait_called = True
        return self

    def get(self) -> Any:
        return self._detail


class FakeTasker:
    def __init__(self, *, succeeded: bool = True, detail: Any = None) -> None:
        self.post_task_calls: list[tuple[str, dict[str, Any]]] = []
        self.task_job = FakeTaskJob(succeeded=succeeded, detail=detail)

    def post_task(self, entry: str, override: dict[str, Any]) -> FakeTaskJob:
        self.post_task_calls.append((entry, override))
        return self.task_job


class FakeWorkspaceManager(WorkspaceManager):
    def __init__(self) -> None:
        super().__init__(Path("."))

    def list_scripts(self) -> list[ScriptInfo]:
        return [ScriptInfo(name="demo.lua", path="scripts/demo.lua", mtime=1.0)]

    def read_script(self, rel_path: str) -> str:
        if rel_path != "scripts/demo.lua":
            raise FileNotFoundError(rel_path)
        return "print('demo')"

    def build_script_run_locator(self, script_path: str) -> ScriptRunLocator:
        project = WorkspaceProject(
            project_id="demo",
            name="demo",
            root_dir="project/demo",
            scripts_dir="project/demo",
            resource_dir="project/demo/resource",
        )
        script = ScriptAsset(
            project_id="demo",
            name=Path(script_path).name,
            relative_path=script_path,
            absolute_path=f"project/demo/{script_path}",
            mtime=0.0,
        )
        return ScriptRunLocator(
            project=project,
            script=script,
            project_root=project.root_dir,
            script_file=script.absolute_path,
            script_dir="project/demo",
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
        )

    def build_pipeline_run_locator(self, project_path: str) -> PipelineRunLocator:
        project = WorkspaceProject(
            project_id="demo",
            name="demo",
            root_dir=project_path,
            scripts_dir=project_path,
            resource_dir=f"{project_path}/resource",
        )
        return PipelineRunLocator(
            project=project,
            project_root=project.root_dir,
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
        )


class FakeIntegrationFacade(IntegrationFacade):
    def __init__(
        self,
        script_runtime_factory: Callable[[], FakeRuntime] | None = None,
        pipeline_tasker_factory: Callable[[], FakeTasker] | None = None,
    ) -> None:
        self.script_runtime_factory = script_runtime_factory or (lambda: FakeRuntime(result={"script": True}))
        self.pipeline_tasker_factory = pipeline_tasker_factory or (lambda: FakeTasker(succeeded=True, detail={"pipeline": True}))

    def create_script_run(
        self,
        locator: ScriptRunLocator,
        controller: Any = None,
        connection_label: str | None = None,
    ) -> ScriptRunContext:
        _ = controller, connection_label
        runtime = self.script_runtime_factory()
        context = ScriptRunContext(
            run_id="script-run-1",
            runtime=cast(Any, runtime),
            maa=build_maa_context(),
            locator=locator,
            stopper=Stopper(),
            status=RunStatus.IDLE,
        )
        runtime.stopper = context.stopper
        return context

    def create_pipeline_run(
        self,
        locator: PipelineRunLocator,
        controller: Any = None,
        connection_label: str | None = None,
    ) -> MaaPipelineRunContext:
        _ = controller, connection_label
        return MaaPipelineRunContext(
            run_id="pipeline-run-1",
            maa=build_maa_context(tasker=self.pipeline_tasker_factory()),
            locator=locator,
            status=RunStatus.IDLE,
        )

    def cancel_script_run(self, context: ScriptRunContext) -> None:
        context.stopper.request_stop()
        context.status = RunStatus.STOPPED

    def stop_pipeline_run(self, context: MaaPipelineRunContext) -> None:
        context.status = RunStatus.STOPPED


class ImmediateRuntimeThreadManager(RuntimeThreadManager):
    def spawn(self, target, *, name: str | None = None) -> RuntimeTask:
        task = self.create_task(target, name=name)
        task.thread.run()
        return task


def build_maa_context(tasker: FakeTasker | None = None) -> MaaContext:
    return MaaContext(
        paths=MaaPaths(library_dir=Path("."), resource_dir=Path(".")),
        state=MaaContextState(),
        tasker=tasker,
    )


def build_facade(
    *,
    script_runtime_factory: Callable[[], FakeRuntime] | None = None,
    pipeline_tasker_factory: Callable[[], FakeTasker] | None = None,
) -> ControlFacade:
    facade = ControlFacade()
    facade.state_mgr = StateManager()
    facade.workspace_mgr = FakeWorkspaceManager()
    integration = FakeIntegrationFacade(
        script_runtime_factory=script_runtime_factory,
        pipeline_tasker_factory=pipeline_tasker_factory,
    )
    facade.exec_mgr.integration_facade = integration
    facade.exec_mgr.script_use_case = facade.exec_mgr.script_use_case.__class__(
        integration,
        thread_manager=ImmediateRuntimeThreadManager(),
        workspace_manager=facade.workspace_mgr,
    )
    facade.exec_mgr.pipeline_use_case = facade.exec_mgr.pipeline_use_case.__class__(
        integration,
        thread_manager=ImmediateRuntimeThreadManager(),
        workspace_manager=facade.workspace_mgr,
    )
    facade.exec_mgr.script_use_case.state_manager = facade.state_mgr
    facade.exec_mgr.pipeline_use_case.state_manager = facade.state_mgr
    return facade


def test_control_facade_workspace_entrypoints() -> None:
    facade = build_facade()

    scripts = facade.list_scripts()
    content = facade.read_script("scripts/demo.lua")

    assert len(scripts) == 1
    assert scripts[0].path == "scripts/demo.lua"
    assert content == "print('demo')"


def test_control_facade_run_script_updates_task_and_result() -> None:
    facade = build_facade(script_runtime_factory=lambda: FakeRuntime(result={"ok": True}))

    task_id = facade.run_script("scripts/demo.lua", "return 1", "ADB:1")
    task = facade.get_task_info(task_id)

    assert task is not None
    assert task.kind == "script"
    assert task.status == "success"
    assert task.result == {"ok": True}


def test_control_facade_task_view_entrypoints() -> None:
    facade = build_facade(script_runtime_factory=lambda: FakeRuntime(result={"ok": True}))

    task_id = facade.run_script("scripts/demo.lua", "return 1", "ADB:1")
    task = facade.get_task_info(task_id)
    assert task is not None
    task.summary["entry"] = "scripts.demo"
    task.log_buffer = [
        {"level": "info", "message": "started"},
        {"level": "warning", "message": "warn line"},
    ]
    task.print_buffer = ["hello", 123]

    task_views = facade.list_task_views()
    detail = facade.get_task_detail_view(task_id)
    logs = facade.get_task_logs(task_id)
    output = facade.get_task_output(task_id)

    assert len(task_views) == 1
    assert task_views[0].task_id == task_id
    assert task_views[0].name == "scripts/demo.lua"
    assert task_views[0].capabilities.has_logs is True
    assert task_views[0].capabilities.has_output is True
    assert detail is not None
    assert detail.summary["entry"] == "scripts.demo"
    assert detail.capabilities.can_remove is True
    assert logs is not None
    assert [item.level for item in logs.items] == ["INFO", "WARNING"]
    assert [item.message for item in logs.items] == ["started", "warn line"]
    assert output is not None
    assert output.items == ["hello", "123"]


def test_control_facade_task_output_view_exposes_limit_metadata() -> None:
    facade = build_facade(script_runtime_factory=lambda: FakeRuntime(result={"ok": True}))

    task_id = facade.run_script("scripts/demo.lua", "return 1", "ADB:1")
    task = facade.get_task_info(task_id)

    assert task is not None
    buffer = TaskOutputBuffer(max_lines=3)
    buffer.append("1")
    buffer.append("2")
    buffer.append("3")
    buffer.append("4")
    task.print_buffer = buffer

    output = facade.get_task_output(task_id)

    assert output is not None
    assert output.items == ["2", "3", "4"]
    assert output.max_lines == 3
    assert output.total_lines == 4
    assert output.version > 0


def test_control_facade_run_pipeline_updates_task_and_result() -> None:
    facade = build_facade(pipeline_tasker_factory=lambda: FakeTasker(succeeded=True, detail={"pipeline": True}))

    task_id = facade.run_pipeline("entry.main", {"node": {"x": 1}}, "ADB:2", "project/demo")
    task = facade.get_task_info(task_id)

    assert task is not None
    assert task.kind == "pipeline"
    assert task.status == "success"
    assert task.result == {"pipeline": True}


def test_control_facade_system_state_contains_started_tasks() -> None:
    facade = build_facade(script_runtime_factory=lambda: FakeRuntime(result={"ok": True}))

    task_id = facade.run_script("scripts/demo.lua", "return 1", "ADB:1")
    state = facade.get_system_state()

    assert any(task.task_id == task_id for task in state.active_tasks)


def test_control_facade_device_overview_entrypoint() -> None:
    facade = build_facade()

    overview = facade.get_device_overview()

    assert overview.connection.initialized is True
    assert overview.adb.summary == "未发现可用 ADB 设备"
    assert overview.desktop.summary == "未发现可控Windows 本地窗口"
    assert getattr(overview, "browser").summary == "已配置 2 个浏览器设备"



def test_control_facade_device_overview_marks_mumu_adb_as_emulator() -> None:
    facade = build_facade()
    facade.device_facade._adb_raw = [
        {
            "name": "MuMu模拟器",
            "adb_path": "adb.exe",
            "address": "127.0.0.1:7555",
            "config": {
                "extras": {
                    "mumu": {
                        "enable": True,
                        "path": "xxx",
                        "lib": "shell",
                        "index": 0,
                        "app_package": "com.example.app",
                        "app_cloned_index": 0,
                    }
                }
            },
            "mumu": {
                "enable": True,
                "path": "xxx",
                "lib": "shell",
                "index": 0,
                "app_package": "com.example.app",
                "app_cloned_index": 0,
            },
            "kind": "emulator",
            "emulator_type": "mumu",
        }
    ]

    overview = facade.get_device_overview()

    assert overview.adb.total == 1
    assert overview.adb.items[0].kind == "emulator"
    assert overview.adb.items[0].tags == ["mumu", "emulator"]



def test_control_facade_connect_emulator_device_uses_mumu_config(mocker) -> None:
    from mluascript.maa.config.models import AdbDeviceConfig
    from mluascript.maa.connections.models import MuMuConfig

    facade = build_facade()
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_adb", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_get_device_config",
        return_value=MaaDeviceConfig(
            adb_devices=[
                AdbDeviceConfig(
                    name="MuMu模拟器",
                    address="127.0.0.1:7555",
                    mumu=MuMuConfig(
                        enable=True,
                        path="xxx",
                        lib="shell",
                        index=0,
                        app_package="com.example.app",
                        app_cloned_index=0,
                    ),
                )
            ]
        ),
    )
    mocker.patch.object(facade.device_facade, "_resolve_default_adb_path", return_value="./adb/adb.exe")

    result = facade.connect_device("emulator:0")

    assert result.ok is True
    assert result.message == "已连接模拟器设备: MuMu模拟器"
    params = mock_connect.call_args.args[1]
    assert params.adb_path == "./adb/adb.exe"


def test_control_facade_manual_connect_adb_reuses_discovered_input_methods(mocker) -> None:
    facade = build_facade()
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_adb", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_resolve_default_adb_path",
        return_value="fallback-adb.exe",
    )
    facade.device_facade._adb_raw = [
        {
            "name": "Android",
            "adb_path": "discovered-adb.exe",
            "address": "192.168.1.245",
            "screencap_methods": 7,
            "input_methods": 6,
            "config": {"agent": "x"},
        }
    ]

    result = facade.connect_adb("192.168.1.245")

    assert result.ok is True
    params = mock_connect.call_args.args[1]
    assert params.adb_path == "discovered-adb.exe"
    assert params.address == "192.168.1.245"
    assert params.screencap_methods == 7
    assert params.input_methods == 4
    assert params.config == {"agent": "x"}
    assert [call.args[1].input_methods for call in mock_connect.call_args_list] == [4]


def test_control_facade_manual_connect_adb_discovers_device_when_cache_empty(mocker) -> None:
    facade = build_facade()
    facade.device_facade._adb_raw = []
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_adb", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_resolve_default_adb_path",
        return_value="fallback-adb.exe",
    )
    mocker.patch(
        "mluascript.control.devices.facade.find_adb_devices",
        return_value=[
            {
                "name": "Android",
                "adb_path": "found-adb.exe",
                "address": "192.168.1.245",
                "screencap_methods": 5,
                "input_methods": 4,
                "config": {"extras": {"demo": True}},
            }
        ],
    )

    result = facade.connect_adb("192.168.1.245")

    assert result.ok is True
    params = mock_connect.call_args.args[1]
    assert params.adb_path == "found-adb.exe"
    assert params.screencap_methods == 5
    assert params.input_methods == 4
    assert params.config == {"extras": {"demo": True}}
    assert [call.args[1].input_methods for call in mock_connect.call_args_list] == [4]


def test_control_facade_manual_connect_adb_forces_touch_backends_without_discovery(mocker) -> None:
    facade = build_facade()
    facade.device_facade._adb_raw = []
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_adb", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_resolve_default_adb_path",
        return_value="fallback-adb.exe",
    )
    mocker.patch("mluascript.control.devices.facade.find_adb_devices", return_value=[])

    result = facade.connect_adb("192.168.1.245:5555")

    assert result.ok is True
    params = mock_connect.call_args.args[1]
    assert params.adb_path == "fallback-adb.exe"
    assert params.address == "192.168.1.245:5555"
    assert params.input_methods == 4
    assert [call.args[1].input_methods for call in mock_connect.call_args_list] == [4]


def test_control_facade_manual_connect_adb_rewrites_default_discovery_methods(mocker) -> None:
    facade = build_facade()
    facade.device_facade._adb_raw = [
        {
            "name": "Android",
            "adb_path": "found-adb.exe",
            "address": "192.168.1.245:5555",
            "screencap_methods": 5,
            "input_methods": -9,
            "config": {"extras": {"demo": True}},
        }
    ]
    mock_session = MagicMock()
    mock_connect = mocker.patch(
        "mluascript.control.devices.facade.connect_adb",
        side_effect=[RuntimeError("maatouch failed"), RuntimeError("minitouch failed"), mock_session],
    )

    result = facade.connect_adb("192.168.1.245:5555")

    assert result.ok is True
    assert [call.args[1].input_methods for call in mock_connect.call_args_list] == [4, 2, 6]


def test_control_facade_manual_connect_adb_returns_success_on_maatouch_first_try(mocker) -> None:
    facade = build_facade()
    facade.device_facade._adb_raw = []
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_adb", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_resolve_default_adb_path",
        return_value="fallback-adb.exe",
    )
    mocker.patch("mluascript.control.devices.facade.find_adb_devices", return_value=[])

    result = facade.connect_adb("192.168.1.245:5555")

    assert result.ok is True
    assert [call.args[1].input_methods for call in mock_connect.call_args_list] == [4]



def test_control_facade_device_overview_contains_visible_browser_devices() -> None:
    from mluascript.maa.config.models import BrowserDeviceConfig

    facade = build_facade()
    facade.device_facade._get_device_config = lambda: MaaDeviceConfig(
        browser_devices=[
            BrowserDeviceConfig(name="Chrome", type="chrome", debug_url="http://127.0.0.1:9222"),
            BrowserDeviceConfig(name="Invalid", type="", debug_url=""),
        ]
    )

    overview = facade.get_device_overview()
    browser_page = getattr(overview, "browser")

    assert browser_page.total == 1
    assert browser_page.items[0].id == "browser:0"
    assert browser_page.items[0].tags == ["chrome", "cdp"]



def test_control_facade_connect_browser_device_uses_browser_config(mocker) -> None:
    from mluascript.maa.config.models import BrowserDeviceConfig

    facade = build_facade()
    mock_session = MagicMock()
    mock_connect = mocker.patch("mluascript.control.devices.facade.connect_browser", return_value=mock_session)
    mocker.patch.object(
        facade.device_facade,
        "_get_device_config",
        return_value=MaaDeviceConfig(
            browser_devices=[
                BrowserDeviceConfig(
                    name="Chrome",
                    type="chrome",
                    debug_url="http://127.0.0.1:9222",
                )
            ]
        ),
    )

    result = facade.connect_device("browser:0")

    assert result.ok is True
    assert result.message == "已连接浏览器设备: Chrome"
    params = mock_connect.call_args.args[1]
    assert params.browser_type == "chrome"
    assert params.url == "http://127.0.0.1:9222"
