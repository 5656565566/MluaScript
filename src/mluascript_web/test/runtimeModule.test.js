import test from 'node:test'
import assert from 'node:assert/strict'

import { createRuntimeActions } from '../src/features/runtime/runtimeModule.js'

function ref(value) {
  return { value }
}

test('stopTasks stops all tasks and refreshes state once', async () => {
  const stopped = []
  let refreshCount = 0
  const state = {
    tasks: ref([
      { task_id: 'a', kind: 'script', status: 'running' },
      { task_id: 'b', kind: 'pipeline', status: 'running' },
    ]),
  }
  let actions
  actions = createRuntimeActions({
    state,
    systemApi: {},
    runApi: {
      async stopTask(taskId, kind) {
        stopped.push([taskId, kind])
      },
    },
    runtimeStreams: {},
    getActions: () => ({
      ...actions,
      async loadState() {
        refreshCount += 1
      },
      setStatus() {},
    }),
  })

  await actions.stopTasks()

  assert.deepEqual(stopped, [['a', 'script'], ['b', 'pipeline']])
  assert.equal(refreshCount, 1)
})

test('stopTask refreshes stale task state before rethrowing a stop failure', async () => {
  const stopError = new Error('任务不存在或已删除')
  let refreshCount = 0
  const state = { tasks: ref([]) }
  let actions
  actions = createRuntimeActions({
    state,
    systemApi: {},
    runApi: {
      async stopTask() {
        throw stopError
      },
    },
    runtimeStreams: {},
    getActions: () => ({
      ...actions,
      async loadState() {
        refreshCount += 1
      },
    }),
  })

  await assert.rejects(actions.stopTask('deleted-task', 'script'), error => error === stopError)
  assert.equal(refreshCount, 1)
})

test('runtime polling refreshes selected task detail only while task manager is active', async () => {
  let detailCalls = 0
  const state = {
    activeView: ref('blockly'),
    autoRefresh: ref(true),
    tasks: ref([]),
    availableScripts: ref([]),
    selectedTaskId: ref('task-a'),
    taskDetailById: ref({}),
  }
  let actions
  actions = createRuntimeActions({
    state,
    systemApi: {
      async listTasks() {
        return { items: [{ task_id: 'task-a' }] }
      },
      async listScripts() {
        return { items: [] }
      },
      async getTaskDetail() {
        detailCalls += 1
        return { task_id: 'task-a' }
      },
    },
    runApi: {},
    runtimeStreams: { stopTask() {} },
    getActions: () => actions,
  })

  await actions.pollRuntime()
  assert.equal(detailCalls, 0)

  state.activeView.value = 'task-manager'
  await actions.pollRuntime()
  assert.equal(detailCalls, 1)
})

test('running a build artifact refreshes only task manager data', async () => {
  const calls = []
  let refreshCount = 0
  const state = {
    selectedSession: ref('ADB:selected'),
  }
  let actions
  actions = createRuntimeActions({
    state,
    systemApi: {},
    runApi: {
      async runArtifact(payload) {
        calls.push(payload)
        return { taskId: 'artifact-task', message: 'started' }
      },
    },
    runtimeStreams: {},
    getActions: () => ({
      ...actions,
      async refreshTaskManagerData() {
        refreshCount += 1
      },
      setStatus() {},
    }),
  })

  const result = await actions.runArtifact('artifact-id')

  assert.equal(result.taskId, 'artifact-task')
  assert.deepEqual(calls, [{ artifactId: 'artifact-id', sessionLabel: 'ADB:selected' }])
  assert.equal(refreshCount, 1)
})

test('opening an artifact readme stores the document and selects the readme tab', async () => {
  const state = {
    artifactReadme: ref(null),
    taskManagerActiveTab: ref('resource-list'),
  }
  const actions = createRuntimeActions({
    state,
    systemApi: {
      async getArtifactReadme(artifactId) {
        assert.equal(artifactId, 'artifact-id')
        return { artifact_id: artifactId, name: 'Demo', path: 'builds/demo.mlspkg', markdown: '# Demo' }
      },
    },
    runApi: {},
    runtimeStreams: {},
    getActions: () => actions,
  })

  const readme = await actions.openArtifactReadme('artifact-id')

  assert.equal(readme.markdown, '# Demo')
  assert.equal(state.artifactReadme.value.name, 'Demo')
  assert.equal(state.taskManagerActiveTab.value, 'artifact-readme')
})
