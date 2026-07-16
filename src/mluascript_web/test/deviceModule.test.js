import test from 'node:test'
import assert from 'node:assert/strict'

import { normalizeConnectionList, normalizeDesktopItems, normalizeDeviceItems } from '../src/api/contracts.js'
import { createDeviceActions } from '../src/features/devices/deviceModule.js'

function ref(value) {
  return { value }
}

function createState() {
  return {
    selectedSession: ref('device'),
    sessions: ref([]),
    adbDevices: ref([]),
    emulatorDevices: ref([]),
    browserDevices: ref([]),
    win32Windows: ref([]),
    adbAddress: ref('127.0.0.1:5555'),
    screenshotBase64: ref(''),
    screenshotPath: ref(''),
    showScreenshot: ref(false),
    devicePreviewWindows: ref([]),
    devicePreviewIntervalMs: ref(1000),
    nextPreviewWindowOffset: ref(0),
  }
}

test('closing a preview during capture cannot leave a timer behind', async () => {
  const state = createState()
  let finishCapture
  const timers = new Map()
  const actions = createDeviceActions({
    state,
    deviceApi: {
      screencap: () => new Promise((resolve) => { finishCapture = resolve }),
    },
    normalizeConnectionList,
    normalizeDesktopItems,
    normalizeDeviceItems,
    scheduler: {
      setTimeout(callback) {
        timers.set(1, callback)
        return 1
      },
      clearTimeout(id) {
        timers.delete(id)
      },
    },
    getActions: () => actions,
  })
  state.devicePreviewWindows.value = [{ id: 'preview', label: 'device', intervalMs: 1000 }]

  const starting = actions.startDevicePreviewLoop('preview')
  await Promise.resolve()
  actions.closeDevicePreviewWindow('preview')
  finishCapture({ imageBase64: 'frame' })
  await starting

  assert.equal(timers.size, 0)
  assert.deepEqual(state.devicePreviewWindows.value, [])
})
