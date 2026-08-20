import test from 'node:test'
import assert from 'node:assert/strict'

import { createAppActions } from '../src/app/appModule.js'

function ref(value) {
  return { value }
}

function createState() {
  return {
    pendingActionCount: ref(0),
    loading: ref(false),
    authenticated: ref(false),
    authChecked: ref(false),
    currentUser: ref(''),
    statusText: ref(''),
    editorSessionHydrated: ref(false),
    lastSessionBlocklyXml: ref(''),
    lastSessionBlocklyFilename: ref(''),
    lastSessionBlocklyPath: ref(''),
    lastSessionLuaCode: ref(''),
    lastSessionLuaFilename: ref(''),
    lastSessionLuaPath: ref(''),
    tasks: ref([]),
    logs: ref([]),
    luaFiles: ref([]),
    availableScripts: ref([]),
    logOrigin: ref('runtime'),
    blocklyEditor: ref(null),
    screenshotPosition: ref({ x: 0, y: 0 }),
    appTheme: ref('system'),
    colorTheme: ref('classic'),
    customColor: ref('#18a058'),
  }
}

function createModule(overrides = {}) {
  const state = overrides.state || createState()
  let actions
  actions = createAppActions({
    state,
    authApi: overrides.authApi || { status: async () => ({ authenticated: false }), login: async () => ({}), logout: async () => ({}) },
    editorApi: overrides.editorApi || { listLuaFiles: async () => ({ items: [] }) },
    logApi: overrides.logApi || { list: async () => ({ items: [] }) },
    systemApi: overrides.systemApi || {
      getBootstrap: async () => ({}),
      listTasks: async () => ({ items: [] }),
      listScripts: async () => ({ items: [] }),
    },
    applyBootstrap: overrides.applyBootstrap || (() => ({ blocklyApplied: false })),
    updateBlocklyTheme: () => {},
    browserWindow: { innerWidth: 1200, dispatchEvent() {}, matchMedia: () => ({ matches: false }) },
    browserDocument: { documentElement: { setAttribute() {}, style: {} } },
    getActions: () => ({
      ...actions,
      invalidateEditorOperations() {},
      stopRuntimeStreams() {},
      stopSelectedTaskStreams() {},
      stopAllDevicePreviewLoops() {},
      refreshSelectedTask: async () => null,
      startRuntimeStreams() {},
      startSelectedTaskStreams() {},
      setStatus() {},
    }),
  })
  return { actions, state }
}

test('handleAction tracks concurrent actions instead of dropping them', async () => {
  const { actions, state } = createModule()
  let releaseFirst
  let releaseSecond
  const first = actions.handleAction(() => new Promise(resolve => { releaseFirst = resolve }))
  const second = actions.handleAction(() => new Promise(resolve => { releaseSecond = resolve }))

  assert.equal(state.pendingActionCount.value, 2)
  assert.equal(state.loading.value, true)
  releaseFirst()
  await first
  assert.equal(state.pendingActionCount.value, 1)
  releaseSecond()
  await second
  assert.equal(state.pendingActionCount.value, 0)
  assert.equal(state.loading.value, false)
})

test('logout invalidates an in-flight authenticated bootstrap', async () => {
  let resolveBootstrap
  let applyCount = 0
  const { actions, state } = createModule({
    authApi: {
      status: async () => ({ authenticated: true, username: 'admin' }),
      login: async () => ({}),
      logout: async () => ({}),
    },
    systemApi: {
      getBootstrap: () => new Promise(resolve => { resolveBootstrap = resolve }),
      listTasks: async () => ({ items: [] }),
      listScripts: async () => ({ items: [] }),
    },
    applyBootstrap: () => {
      applyCount += 1
      return { blocklyApplied: false }
    },
  })

  const checking = actions.checkAuth()
  await Promise.resolve()
  await actions.logout()
  resolveBootstrap({})
  await checking

  assert.equal(state.authenticated.value, false)
  assert.equal(applyCount, 0)
})

test('applyTheme ignores a select option object passed as the color theme', () => {
  const { actions, state } = createModule()

  actions.applyTheme('light', { label: '亮色主题', value: 'light' })

  assert.equal(state.appTheme.value, 'light')
  assert.equal(state.colorTheme.value, 'classic')
})

test('saveCroppedImage uploads a PNG into the current project resources', async () => {
  const state = createState()
  state.currentProject = ref({ key: 'demo-project' })
  let uploaded = null
  let actions
  actions = createAppActions({
    state,
    authApi: { status: async () => ({}), login: async () => ({}), logout: async () => ({}) },
    editorApi: { listLuaFiles: async () => ({ items: [] }) },
    logApi: { list: async () => ({ items: [] }) },
    systemApi: { getBootstrap: async () => ({}), listTasks: async () => ({ items: [] }), listScripts: async () => ({ items: [] }) },
    applyBootstrap: () => ({ blocklyApplied: false }),
    updateBlocklyTheme: () => {},
    browserWindow: { innerWidth: 1200, dispatchEvent() {}, matchMedia: () => ({ matches: false }) },
    browserDocument: { documentElement: { setAttribute() {}, style: {} } },
    getActions: () => ({
      ...actions,
      setStatus() {},
      uploadProjectFile: async (...args) => {
        uploaded = args
        return { path: args[0] }
      },
    }),
  })

  const result = await actions.saveCroppedImage('crop.png', 'iVBORw0KGgo=')

  assert.equal(result.path, 'resources/assets/crop.png')
  assert.equal(uploaded[0], 'resources/assets/crop.png')
  assert.equal(uploaded[1].type, 'image/png')
  assert.equal(uploaded[2], true)

  const nested = await actions.saveCroppedImage('button.png', 'iVBORw0KGgo=', 'resources/assets/ui/dialog')
  assert.equal(nested.path, 'resources/assets/ui/dialog/button.png')
  assert.equal(uploaded[0], 'resources/assets/ui/dialog/button.png')
})
