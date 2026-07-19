import assert from 'node:assert/strict'
import test from 'node:test'

import { createTemplateAutosave } from '../src/ui/templateEditor/templateAutosave.js'

function createScheduler() {
  let nextId = 0
  const callbacks = new Map()
  return {
    setTimeout(callback) {
      nextId += 1
      callbacks.set(nextId, callback)
      return nextId
    },
    clearTimeout(id) {
      callbacks.delete(id)
    },
    runLatest() {
      const entry = [...callbacks.entries()].at(-1)
      if (!entry) return
      callbacks.delete(entry[0])
      entry[1]()
    },
  }
}

test('模板自动保存会防抖并只写入最新快照', async () => {
  const scheduler = createScheduler()
  const saved = []
  const autosave = createTemplateAutosave({
    scheduler,
    save: async snapshot => saved.push(snapshot),
  })

  autosave.schedule('first')
  autosave.schedule('latest')
  scheduler.runLatest()
  await autosave.flush()

  assert.deepEqual(saved, ['latest'])
})

test('模板自动保存串行处理进行中与后续快照', async () => {
  const scheduler = createScheduler()
  const saved = []
  let releaseFirst
  const autosave = createTemplateAutosave({
    scheduler,
    save: snapshot => {
      saved.push(snapshot)
      if (snapshot !== 'first') return Promise.resolve()
      return new Promise(resolve => { releaseFirst = resolve })
    },
  })

  autosave.schedule('first')
  scheduler.runLatest()
  await Promise.resolve()
  autosave.schedule('second')
  const flushing = autosave.flush()
  releaseFirst()
  await flushing

  assert.deepEqual(saved, ['first', 'second'])
})
