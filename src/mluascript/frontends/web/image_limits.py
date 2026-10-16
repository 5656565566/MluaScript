from __future__ import annotations

import asyncio

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


MAX_RECOGNITION_REQUEST_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_CONCURRENT_RECOGNITIONS = 2


class RecognitionImageLimitsMiddleware:
    """在 JSON 解析和图片解码前约束识图请求，不限制模型等其他文件上传。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_RECOGNITIONS)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").removeprefix(scope.get("root_path", "")).rstrip("/").split("/")
        if (
            scope["type"] != "http" or scope["method"] != "POST"
            or len(path) != 5 or path[1:3] != ["api", "projects"] or path[4] != "recognize-image"
        ):
            await self.app(scope, receive, send)
            return

        message = "识图请求体不能超过 16 MiB"
        try:
            declared_size = int(dict(scope.get("headers", [])).get(b"content-length", b"0"))
        except ValueError:
            declared_size = 0
        if declared_size > MAX_RECOGNITION_REQUEST_BYTES:
            await JSONResponse({"detail": message}, status_code=413)(scope, receive, send)
            return

        async with self._slots:
            size = 0

            async def receive_limited() -> Message:
                nonlocal size
                event = await receive()
                if event["type"] == "http.request":
                    size += len(event.get("body", b""))
                    if size > MAX_RECOGNITION_REQUEST_BYTES:
                        raise HTTPException(status_code=413, detail=message)
                return event

            await self.app(scope, receive_limited, send)
