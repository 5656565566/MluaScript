from __future__ import annotations

from mluascript.shared.logging import logger

from maa.controller import AdbController
from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum

from ..lifecycle.binding import bind_controller
from ..lifecycle.runtime import MaaContext
from .models import AdbConnectionParams, ConnectionInfo
from .session import ConnectionSession


def connect_adb(context: MaaContext, params: AdbConnectionParams) -> ConnectionSession:
    """建立 ADB 连接"""
    logger.info(f"Prepare adb connection: {params.address}")

    kwargs = {}
    if params.screencap_methods is not None and params.screencap_methods != 0:
        kwargs["screencap_methods"] = params.screencap_methods
    if params.input_methods is not None and params.input_methods != 0:
        kwargs["input_methods"] = params.input_methods

    merged_config = params.config.copy() if params.config else {}

    if params.mumu and params.mumu.enable:
        kwargs["screencap_methods"] = int(MaaAdbScreencapMethodEnum.EmulatorExtras)
        kwargs["input_methods"] = int(MaaAdbInputMethodEnum.EmulatorExtras)
        merged_config.setdefault("extras", {})
        merged_config["extras"].setdefault("mumu", {})
        merged_config["extras"]["mumu"]["enable"] = params.mumu.enable
        merged_config["extras"]["mumu"]["path"] = params.mumu.path
        if params.mumu.lib:
            merged_config["extras"]["mumu"]["lib"] = params.mumu.lib
        merged_config["extras"]["mumu"]["index"] = params.mumu.index
        if params.mumu.app_package:
            merged_config["extras"]["mumu"]["app_package"] = params.mumu.app_package
        merged_config["extras"]["mumu"]["app_cloned_index"] = params.mumu.app_cloned_index

    controller = AdbController(
        adb_path=params.adb_path,
        address=params.address,
        config=merged_config,
        **kwargs
    )
    
    job = controller.post_connection()
    job.wait()
    
    if not getattr(job, "succeeded", False):
        logger.error(f"Adb controller post_connection failed for {params.address}")
        raise RuntimeError(f"Adb controller connect failed: {params.address}")

    screencap_job = controller.post_screencap()
    screencap_job.wait()
    if not getattr(screencap_job, "succeeded", False):
        logger.error(f"Adb controller screen capture failed for {params.address}")
        raise RuntimeError(f"Adb controller connect successful but screencap failed: {params.address}")

    bind_controller(context, controller)
    info = ConnectionInfo(kind="adb", label=f"ADB:{params.address}", meta={"address": params.address, "adb_path": params.adb_path})
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)
