import test from 'node:test'
import assert from 'node:assert/strict'

import { createRuntimeStreams } from '../src/features/runtime/runtimeStreams.js'

class FakeSource {
  listeners = new Map()
  closed = false

  addEventListener(name, handler) {
    this.listeners.set(name, handler)
  }

  emit(name, payload = {}) {
    this.listeners.get(name)?.({ data: JSON.stringify(payload) })
  }

  close() {
    this.closed = true
  }
}

function createHarness() {
  const sources = []
  const streamApi = {
    createLogsStream() {
      const source = new FakeSource()
      sources.push(source)
      return source
    },
    createTaskLogsStream() {
      const source = new FakeSource()
      sources.push(source)
      return source
    },
    createTaskOutputStream() {
      const source = new FakeSource()
      sources.push(source)
      return source
    },
  }
  const timers = new Map()
  let timerId = 0
  const scheduler = {
    setTimeout(callback) {
      timerId += 1
      timers.set(timerId, callback)
      return timerId
    },
    clearTimeout(id) {
      timers.delete(id)
    },
  }
  return { scheduler, sources, streamApi, timers }
}

test('runtime logs are bounded and stop closes the owned stream', () => {
  const harness = createHarness()
  let logs = []
  const streams = createRuntimeStreams({
    ...harness,
    isAuthenticated: () => true,
    getSelectedTaskId: () => '',
    getLogParams: () => ({}),
    onLogsSnapshot: (items) => { logs = items },
    onLog: (item, limit) => { logs = [...logs, item].slice(-limit) },
    onTaskLogs: () => {},
    onTaskOutput: () => {},
    maxLogs: 2,
  })

  streams.startLogs()
  harness.sources[0].emit('snapshot', { items: [1, 2, 3] })
  harness.sources[0].emit('log', 4)
  assert.deepEqual(logs, [3, 4])

  streams.stopLogs()
  assert.equal(harness.sources[0].closed, true)
})

test('switching selected tasks closes both previous task streams', () => {
  const harness = createHarness()
  let selectedTaskId = 'a'
  const streams = createRuntimeStreams({
    ...harness,
    isAuthenticated: () => true,
    getSelectedTaskId: () => selectedTaskId,
    getLogParams: () => ({}),
    onLogsSnapshot: () => {},
    onLog: () => {},
    onTaskLogs: () => {},
    onTaskOutput: () => {},
  })

  streams.startTask('a')
  selectedTaskId = 'b'
  streams.startTask('b')

  assert.equal(harness.sources[0].closed, true)
  assert.equal(harness.sources[1].closed, true)
  assert.equal(harness.sources[2].closed, false)
  assert.equal(harness.sources[3].closed, false)
})
