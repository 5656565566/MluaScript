from pathlib import Path
from types import SimpleNamespace

import pytest

from mluascript.control.integration import script_resources as resources
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.lifecycle.resources import override_pipeline
from mluascript.maa.types import MaaPaths


@pytest.fixture
def pool(monkeypatch, tmp_path):
    resources.clear_idle_script_runtime()
    paths = MaaPaths(library_dir=tmp_path / 'lib', resource_dir=tmp_path / 'resources', model_dir=tmp_path / 'model')
    initialized = []

    def initialize(context):
        context.resource = SimpleNamespace(override_pipeline=lambda value: True)
        context.tasker = SimpleNamespace(running=False, stopping=False, clear_cache=lambda: True)
        initialized.append(context)
        context.mark_loaded()
        return context

    monkeypatch.setattr(resources, 'resolve_maa_paths', lambda: paths)
    monkeypatch.setattr(resources, 'create_maa_context', lambda: MaaContext(paths=paths))
    monkeypatch.setattr(resources, 'initialize_maa_runtime', initialize)
    yield paths, initialized
    resources.clear_idle_script_runtime()


def test_repeated_runs_reuse_native_resources_with_fresh_context_state(pool):
    paths, initialized = pool
    controller = object()
    first = resources.acquire_script_maa_context(paths.resource_dir, controller)
    native = first.tasker, first.resource
    first.controller = controller
    first.state.extras['active_touch_contacts'] = {1}
    assert resources.release_script_resources(first)
    assert first.tasker is None and first.resource is None and first.controller is None
    for _ in range(30):
        context = resources.acquire_script_maa_context(paths.resource_dir, controller)
        assert (context.tasker, context.resource) == native
        assert context.state.extras.get('active_touch_contacts') is None
        context.controller = controller
        assert resources.release_script_resources(context)
    assert len(initialized) == 1


def test_active_resources_are_never_shared_and_only_one_idle_instance_is_retained(pool):
    paths, initialized = pool
    controller = object()
    first = resources.acquire_script_maa_context(paths.resource_dir, controller)
    second = resources.acquire_script_maa_context(paths.resource_dir, controller)
    assert first.tasker is not second.tasker
    latest = second.tasker
    first.controller = second.controller = controller
    assert resources.release_script_resources(first)
    assert resources.release_script_resources(second)
    again = resources.acquire_script_maa_context(paths.resource_dir, controller)
    assert again.tasker is latest
    assert len(initialized) == 2


@pytest.mark.parametrize('change', ['controller', 'project', 'model', 'pipeline'])
def test_resource_changes_invalidate_idle_instances(pool, change, tmp_path):
    paths, initialized = pool
    paths.model_dir.mkdir()
    model = paths.model_dir / 'model.onnx'
    model.write_bytes(b'old')
    controller = object()
    first = resources.acquire_script_maa_context(paths.resource_dir, controller)
    first.controller = controller
    if change == 'pipeline':
        override_pipeline(first, {'changed': {}})
    assert resources.release_script_resources(first)
    if change == 'model':
        model.write_bytes(b'new model')
    second = resources.acquire_script_maa_context(tmp_path / 'other' if change == 'project' else paths.resource_dir,
                                                object() if change == 'controller' else controller)
    assert len(initialized) == 2
    assert second is not first


def test_busy_resource_is_retained_until_the_native_task_has_finished(pool):
    paths, _ = pool
    context = resources.acquire_script_maa_context(paths.resource_dir, None)
    context.tasker.running = True
    tasker = context.tasker
    assert resources.release_script_resources(context) is False
    assert context.tasker is tasker
    context.tasker.running = False
    assert resources.release_script_resources(context) is True
