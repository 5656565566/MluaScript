import test from 'node:test'
import assert from 'node:assert/strict'

import { createProjectActions } from '../src/features/projects/projectModule.js'

function ref(value) {
  return { value }
}

function createState() {
  const activeFile = { path: 'scripts/main.lua', encoding: 'utf-8', mtime: 1, content: 'old' }
  return {
    projects: ref([]),
    currentProject: ref({ key: 'project-key' }),
    currentManifest: ref({}),
    projectTree: ref([]),
    projectOpenFiles: ref([{
      path: 'scripts/main.lua',
      file: activeFile,
      content: 'old',
      dirty: true,
      generatedLua: '',
      generatedLuaStale: false,
      blocklyDiagnostics: [],
    }]),
    projectSelectedPath: ref('scripts/main.lua'),
    projectFile: ref(activeFile),
    projectFileContent: ref('old'),
    projectFileDirty: ref(true),
    projectGeneratedLua: ref(''),
    projectGeneratedLuaStale: ref(false),
    projectBlocklyDiagnostics: ref([]),
    projectLuaPreviewVisible: ref(false),
    projectDiagnostics: ref([]),
    projectLoading: ref(false),
    projectFileOperationLoading: ref(false),
    projectBuildLoading: ref(false),
    projectBuildResult: ref(null),
    projectDebugLoading: ref(false),
    projectDebugTaskByKey: ref({}),
    selectedSession: ref('ADB:selected'),
  }
}

test('Blockly project debugging compiles every module into the virtual scripts tree', async () => {
  const state = createState()
  state.currentProject.value = { key: 'project-key', project_type: 'blockly-package', primary_path: 'blockly/main.xml' }
  state.projectTree.value = [
    { kind: 'file', path: 'blockly/main.xml' },
    { kind: 'file', path: 'blockly/lib/helper.xml' },
  ]
  state.projectOpenFiles.value = []
  state.projectSelectedPath.value = ''
  state.projectFile.value = null
  state.projectFileContent.value = ''
  state.projectFileDirty.value = false
  const debugCalls = []
  const projectApi = {
    readFile: async (_key, path) => ({ path, encoding: 'utf-8', content: `<xml data-path="${path}"></xml>` }),
    debug: async (_key, payload) => {
      debugCalls.push(payload)
      return { taskId: 'debug-1', kind: 'script', entryPath: payload.entryPath }
    },
  }
  let fullStateReloads = 0
  let taskRefreshes = 0
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    compileBlocklyXml: xml => ({ code: `-- ${xml}`, diagnostics: [], stale: false }),
    getActions: () => ({
      ...actions,
      loadState: async () => { fullStateReloads += 1 },
      refreshTaskManagerData: async () => { taskRefreshes += 1 },
      setStatus() {},
    }),
  })

  await actions.debugProject({ entryPath: 'blockly/main.xml' })

  assert.equal(debugCalls[0].entryPath, 'scripts/main.lua')
  assert.equal(debugCalls[0].sessionLabel, 'ADB:selected')
  assert.match(debugCalls[0].sourceOverrides['scripts/lib/helper.lua'], /blockly\/lib\/helper\.xml/)
  assert.equal(state.projectDebugTaskByKey.value['project-key'].taskId, 'debug-1')
  assert.equal(taskRefreshes, 1)
  assert.equal(fullStateReloads, 0)
})

test('project saves are serialized without overwriting a newer draft', async () => {
  const state = createState()
  const writes = []
  let resolveFirst
  const projectApi = {
    writeFile: async (_key, payload) => {
      writes.push(payload)
      if (writes.length === 1) {
        return await new Promise((resolve) => { resolveFirst = resolve })
      }
      return { path: payload.path, encoding: 'utf-8', mtime: 3, content: payload.content }
    },
    listTree: async () => ({ items: [] }),
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus() {} }),
  })

  const first = actions.saveProjectFile()
  await Promise.resolve()
  state.projectFileContent.value = 'newer draft'
  state.projectFileDirty.value = true
  const second = actions.saveProjectFile()
  resolveFirst({ path: 'scripts/main.lua', encoding: 'utf-8', mtime: 2, content: 'old' })
  await Promise.all([first, second])

  assert.equal(writes.length, 2)
  assert.equal(writes[1].expectedMtime, 2)
  assert.equal(writes[1].content, 'newer draft')
  assert.equal(state.projectFileContent.value, 'newer draft')
  assert.equal(state.projectFileDirty.value, false)
})

test('project tabs retain independent unsaved drafts without reloading an open file', async () => {
  const state = createState()
  const reads = []
  const projectApi = {
    readFile: async (_key, path) => {
      reads.push(path)
      return { path, encoding: 'utf-8', mtime: 1, content: `loaded:${path}` }
    },
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus() {} }),
  })

  await actions.selectProjectFile({ kind: 'file', path: 'scripts/second.lua' })
  actions.setProjectFileContent('second draft')
  await actions.selectProjectFile({ kind: 'file', path: 'scripts/main.lua' })
  assert.equal(state.projectFileContent.value, 'old')
  assert.equal(state.projectFileDirty.value, true)

  await actions.selectProjectFile({ kind: 'file', path: 'scripts/second.lua' })
  assert.equal(state.projectFileContent.value, 'second draft')
  assert.equal(state.projectFileDirty.value, true)
  assert.deepEqual(reads, ['scripts/second.lua'])
})

test('silent project saves update state without publishing a success message', async () => {
  const state = createState()
  const statuses = []
  const projectApi = {
    writeFile: async (_key, payload) => ({
      path: payload.path,
      encoding: 'utf-8',
      mtime: 2,
      content: payload.content,
    }),
    listTree: async () => ({ items: [] }),
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus: (...args) => statuses.push(args) }),
  })

  await actions.saveProjectFile({ notify: false })

  assert.equal(state.projectFileDirty.value, false)
  assert.deepEqual(statuses, [])
})

test('manual save reports success when autosave already persisted the file', async () => {
  const state = createState()
  state.projectOpenFiles.value[0].dirty = false
  state.projectFileDirty.value = false
  const statuses = []
  const projectApi = {
    writeFile: async () => { throw new Error('clean files must not be written again') },
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus: (...args) => statuses.push(args) }),
  })

  await actions.saveProjectFile()

  assert.deepEqual(statuses, [['已保存 scripts/main.lua', 'success']])
})

test('renaming a custom project path keeps open tabs and the active file synchronized', async () => {
  const state = createState()
  const projectApi = {
    renamePath: async (_key, payload) => ({
      path: `scripts/${payload.newName}`,
      name: payload.newName,
      kind: 'file',
      size: 3,
      mtime: 2,
    }),
    listTree: async () => ({ items: [] }),
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus() {} }),
  })

  await actions.renameProjectPath('scripts/main.lua', 'renamed.lua')

  assert.equal(state.projectOpenFiles.value[0].path, 'scripts/renamed.lua')
  assert.equal(state.projectSelectedPath.value, 'scripts/renamed.lua')
  assert.equal(state.projectFile.value.path, 'scripts/renamed.lua')
  assert.equal(state.projectFile.value.name, 'renamed.lua')
})

test('moving a directory remaps every open child tab and manifest reference without losing drafts', async () => {
  const state = createState()
  const secondFile = { path: 'scripts/lib/helper.lua', encoding: 'utf-8', mtime: 1, content: 'disk helper' }
  state.currentProject.value.primary_path = 'scripts/main.lua'
  state.currentManifest.value = {
    entrypoints: { main: { script: 'scripts/main.lua', models: { helper: 'scripts/lib/helper.lua' } } },
    resources: {},
    models: {},
  }
  state.projectOpenFiles.value.push({
    path: secondFile.path,
    file: secondFile,
    content: 'dirty helper',
    dirty: true,
    generatedLua: '',
    generatedLuaStale: false,
    blocklyDiagnostics: [],
  })
  const moves = []
  const projectApi = {
    movePath: async (_key, payload) => {
      moves.push(payload)
      return { path: 'source', name: 'source', kind: 'directory' }
    },
    listTree: async () => ({ items: [] }),
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus() {} }),
  })

  await actions.moveProjectPath('scripts', 'source')

  assert.deepEqual(moves, [{ sourcePath: 'scripts', destinationPath: 'source' }])
  assert.deepEqual(state.projectOpenFiles.value.map(tab => tab.path), ['source/main.lua', 'source/lib/helper.lua'])
  assert.deepEqual(state.projectOpenFiles.value.map(tab => tab.content), ['old', 'dirty helper'])
  assert.deepEqual(state.projectOpenFiles.value.map(tab => tab.dirty), [true, true])
  assert.equal(state.projectSelectedPath.value, 'source/main.lua')
  assert.equal(state.currentProject.value.primary_path, 'source/main.lua')
  assert.equal(state.currentManifest.value.entrypoints.main.script, 'source/main.lua')
  assert.equal(state.currentManifest.value.entrypoints.main.models.helper, 'source/lib/helper.lua')
})

test('Blockly single-file builds send generated Lua and source identity', async () => {
  const state = createState()
  state.currentProject.value = {
    key: 'project-key',
    project_type: 'blockly-file',
    primary_path: 'demo.xml',
  }
  state.projectSelectedPath.value = 'demo.xml'
  state.projectFile.value = { path: 'demo.xml', encoding: 'utf-8', mtime: 1, content: '<xml />' }
  state.projectFileContent.value = '<xml />'
  state.projectFileDirty.value = false
  state.projectOpenFiles.value = [{
    path: 'demo.xml',
    file: state.projectFile.value,
    content: '<xml />',
    dirty: false,
    generatedLua: "print('generated')",
    generatedLuaStale: false,
    blocklyDiagnostics: [],
  }]
  state.projectGeneratedLua.value = "print('generated')"
  const builds = []
  const projectApi = {
    build: async (_key, payload) => {
      builds.push(payload)
      return { filename: 'demo.lua' }
    },
  }
  let actions
  actions = createProjectActions({
    state,
    projectApi,
    getActions: () => ({ ...actions, setStatus() {} }),
  })

  await actions.buildProject()

  assert.deepEqual(builds, [{ generatedLua: "print('generated')", generatedFrom: 'demo.xml' }])
})
