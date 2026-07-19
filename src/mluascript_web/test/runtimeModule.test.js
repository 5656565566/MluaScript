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
