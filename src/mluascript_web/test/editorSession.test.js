import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyEditorSession,
  buildEditorSessionPayload,
} from '../src/features/editor/editorSession.js'
import { createSaveCoordinator } from '../src/features/editor/saveCoordinator.js'

function ref(value) {
  return { value }
}

function createState() {
  return {
    editorSessionHydrated: ref(false),
    lastSavedBlocklyXml: ref(''),
    lastSessionBlocklyXml: ref(''),
    lastSessionBlocklyFilename: ref(''),
    lastSessionBlocklyPath: ref(''),
    lastSessionLuaCode: ref(''),
    lastSessionLuaFilename: ref(''),
    lastSessionLuaPath: ref(''),
    blocklyXml: ref(''),
    blocklyFilename: ref('blockly.xml'),
    blocklySavePath: ref(''),
    blocklyDocumentMtime: ref(null),
    blocklySaveMode: ref('create'),
    luaCode: ref(''),
    filename: ref('script.lua'),
    savePath: ref(''),
    luaDocumentMtime: ref(null),
    luaSaveMode: ref('create'),
  }
}

test('editor session payload preserves persistence metadata', () => {
  const state = createState()
  state.blocklyXml.value = '<xml />'
  state.blocklyDocumentMtime.value = 12.5
  state.blocklySaveMode.value = 'update'
  state.luaDocumentMtime.value = 23.5
  state.luaSaveMode.value = 'update'

  const payload = buildEditorSessionPayload(state)
  assert.equal(payload.blocklyDocument.mtime, 12.5)
  assert.equal(payload.blocklyDocument.saveMode, 'update')
  assert.equal(payload.luaDocument.mtime, 23.5)
  assert.equal(payload.luaDocument.saveMode, 'update')
})

test('hydration does not overwrite an existing local draft', () => {
  const state = createState()
  applyEditorSession(state, {
    blocklyDocument: { xml: '<xml>server</xml>', filename: 'a.xml', path: 'a.xml' },
    luaDocument: { content: 'server', filename: 'a.lua', path: 'a.lua' },
  })
  state.blocklyXml.value = '<xml>local</xml>'

  const result = applyEditorSession(state, {
    blocklyDocument: { xml: '<xml>new-server</xml>', filename: 'a.xml', path: 'a.xml' },
    luaDocument: { content: 'server', filename: 'a.lua', path: 'a.lua' },
  })

  assert.equal(result.blocklyApplied, false)
  assert.equal(state.blocklyXml.value, '<xml>local</xml>')
})

test('save coordinator serializes saves and ignores stale document commits', async () => {
  const coordinator = createSaveCoordinator()
  const commits = []
  let resolveFirst

  const first = coordinator.enqueue({
    execute: () => new Promise((resolve) => { resolveFirst = resolve }),
    commit: (value) => commits.push(value),
  })
  const second = coordinator.enqueue({
    execute: async () => 'second',
    commit: (value) => commits.push(value),
  })

  coordinator.beginDocumentTransition()
  await Promise.resolve()
  resolveFirst('first')
  await Promise.all([first, second])
  assert.deepEqual(commits, [])

  await coordinator.enqueue({
    execute: async () => 'current',
    commit: (value) => commits.push(value),
  })
  assert.deepEqual(commits, ['current'])
})
