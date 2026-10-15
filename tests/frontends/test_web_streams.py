from __future__ import annotations

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from types import SimpleNamespace

import anyio.to_thread
import httpx
import pytest
import uvicorn

from mluascript.control.state.models import TaskLogEntryView, TaskLogsView, TaskOutputView
from mluascript.frontends.web import app as web_app


class Disconnection:
    disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


def parse_event(value: str) -> tuple[str, dict]:
    name, data = value.strip().split("\ndata: ", 1)
    return name.removeprefix("event: "), json.loads(data)


def test_logs_stream_preserves_snapshot_delta_heartbeat_and_disconnect(monkeypatch) -> None:
    items = [{"formatted": "first", "message": "one"}]

    def snapshot(*, after=None, **kwargs):
        return len(items), list(items[after or 0:])

    monkeypatch.setattr(web_app, "get_log_snapshot", snapshot)

    async def scenario():
        request = Disconnection()
        response = web_app.stream_logs(request=request, replay=3)
        stream = response.body_iterator
        try:
            assert parse_event(await anext(stream)) == ("snapshot", {"items": items})
            items.append({"formatted": "second", "message": "二"})
            assert parse_event(await anext(stream)) == ("log", items[-1])
            assert parse_event(await anext(stream))[0] == "heartbeat"
            request.disconnected = True
            with pytest.raises(StopAsyncIteration):
                await asyncio.wait_for(anext(stream), timeout=2)
        finally:
            await stream.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["logs", "output"])
def test_task_stream_preserves_snapshot_update_and_not_found(monkeypatch, kind) -> None:
    current = TaskLogsView(task_id="task") if kind == "logs" else TaskOutputView(task_id="task")
    state = SimpleNamespace(current=current)
    getter = lambda task_id: state.current
    facade = SimpleNamespace(get_task_logs=getter, get_task_output=getter)
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)

    async def scenario():
        response = getattr(web_app, f"stream_task_{kind}")("task", request=Disconnection())
        stream = response.body_iterator
        try:
            assert parse_event(await anext(stream)) == ("snapshot", current.model_dump())
            if kind == "logs":
                state.current = TaskLogsView(task_id="task", items=[TaskLogEntryView(message="new")])
            else:
                state.current = TaskOutputView(task_id="task", items=["new"], version=1)
            assert parse_event(await anext(stream)) == ("update", state.current.model_dump())
            assert parse_event(await anext(stream))[0] == "heartbeat"
            state.current = None
            assert parse_event(await asyncio.wait_for(anext(stream), timeout=2)) == ("not_found", {"taskId": "task"})
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
        finally:
            await stream.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["logs", "task_logs", "task_output"])
def test_stream_already_disconnected_does_not_read_snapshots(monkeypatch, mocker, kind) -> None:
    logs = mocker.Mock()
    facade = SimpleNamespace(get_task_logs=mocker.Mock(), get_task_output=mocker.Mock())
    monkeypatch.setattr(web_app, "get_log_snapshot", logs)
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)

    async def scenario():
        request = Disconnection()
        request.disconnected = True
        response = web_app.stream_logs(request=request) if kind == "logs" else getattr(web_app, f"stream_{kind}")("task", request=request)
        with pytest.raises(StopAsyncIteration):
            await anext(response.body_iterator)
        logs.assert_not_called()
        facade.get_task_logs.assert_not_called()
        facade.get_task_output.assert_not_called()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["logs", "task_logs", "task_output"])
def test_stream_cancellation_interrupts_idle_wait(monkeypatch, kind) -> None:
    monkeypatch.setattr(web_app, "get_log_snapshot", lambda **kwargs: (0, []))
    monkeypatch.setattr(web_app, "get_control_facade", lambda: SimpleNamespace(
        get_task_logs=lambda task_id: TaskLogsView(task_id=task_id),
        get_task_output=lambda task_id: TaskOutputView(task_id=task_id),
    ))

    async def scenario():
        request = Disconnection()
        response = web_app.stream_logs(request=request) if kind == "logs" else getattr(web_app, f"stream_{kind}")("task", request=request)
        stream = response.body_iterator
        assert parse_event(await anext(stream))[0] == "snapshot"
        assert parse_event(await anext(stream))[0] == "heartbeat"
        pending = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(pending, timeout=0.5)
        await stream.aclose()

    asyncio.run(scenario())


@asynccontextmanager
async def live_server(application):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    address = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(application, log_config=None, access_log=False, lifespan="off", timeout_graceful_shutdown=4))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if serving.done():
                    await serving
                    raise AssertionError("Uvicorn exited before startup")
                await asyncio.sleep(0.01)
        yield address
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=8)
        listener.close()


@pytest.mark.integration
def test_real_sse_connections_do_not_consume_idle_threadpool_tokens(monkeypatch, tmp_path) -> None:
    configuration = SimpleNamespace(
        username="admin", password="test-password", session_secret="0123456789abcdef",
        session_max_age_seconds=3600, project_roots=[str(tmp_path / "projects")],
    )
    monkeypatch.setattr(web_app, "_get_web_config", lambda: configuration)
    monkeypatch.setattr(web_app, "get_log_snapshot", lambda **kwargs: (0, []))
    monkeypatch.setattr(web_app, "get_control_facade", lambda: SimpleNamespace(
        get_task_logs=lambda task_id: TaskLogsView(task_id=task_id),
        get_task_output=lambda task_id: TaskOutputView(task_id=task_id),
    ))
    application = web_app.create_web_app(tmp_path / "dist", runtime_dir=tmp_path)
    active = set()

    @application.middleware("http")
    async def observe_streams(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/streams/") and response.status_code == 200:
            original = response.body_iterator
            token = object()

            async def observe():
                active.add(token)
                try:
                    async for item in original:
                        yield item
                finally:
                    active.discard(token)

            response.body_iterator = observe()
        return response

    @application.get("/_test/metrics")
    async def metrics():
        limiter = anyio.to_thread.current_default_thread_limiter()
        return {"borrowed": limiter.borrowed_tokens, "streams": len(active)}

    application.router.routes.insert(0, application.router.routes.pop())

    async def scenario():
        async with live_server(application) as address:
            limits = httpx.Limits(max_connections=120, max_keepalive_connections=0)
            async with httpx.AsyncClient(base_url=address, timeout=8, limits=limits, trust_env=False) as client:
                assert (await client.get("/api/streams/logs")).status_code == 401
                assert (await client.post("/api/auth/login", json={"username": "admin", "password": "test-password"})).status_code == 200

                async def consume(path, ready):
                    async with client.stream("GET", path) as response:
                        assert response.status_code == 200
                        assert response.headers["content-type"].startswith("text/event-stream")
                        async for line in response.aiter_lines():
                            if line == "event: snapshot":
                                ready.set()

                for count in (80, 24):
                    tasks = []
                    signals = []
                    paths = ["/api/streams/logs", "/api/streams/tasks/task/logs", "/api/streams/tasks/task/output"]
                    try:
                        for index in range(count):
                            ready = asyncio.Event()
                            signals.append(ready)
                            tasks.append(asyncio.create_task(consume(paths[index % 3], ready)))
                        await asyncio.wait_for(asyncio.gather(*(ready.wait() for ready in signals)), timeout=8)
                        observed = (await client.get("/_test/metrics")).json()
                        assert observed == {"borrowed": 0, "streams": count}, observed
                        async with asyncio.timeout(1):
                            assert (await client.get("/api/auth/status")).status_code == 200
                    finally:
                        for task in tasks:
                            task.cancel()
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        assert all(result is None or isinstance(result, asyncio.CancelledError) for result in results), results
                    async with asyncio.timeout(3):
                        while (await client.get("/_test/metrics")).json() != {"borrowed": 0, "streams": 0}:
                            await asyncio.sleep(0.01)

    asyncio.run(scenario())
