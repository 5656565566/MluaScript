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
