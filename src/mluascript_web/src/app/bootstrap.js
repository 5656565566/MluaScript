import { applyEditorSession } from '../features/editor/editorSession'
import { applyWebPreferences } from './preferences'

export function applyBootstrapState({
  state,
  bootstrap,
  normalizeConnectionList,
  normalizeDesktopItems,
  normalizeDeviceItems,
}) {
  const systemState = bootstrap.systemState || {}
  const editorSession = bootstrap.editorSession || {}
  const deviceOverview = bootstrap.deviceOverview || {}
  const taskSummary = bootstrap.taskSummary || {}
  const editorHydration = applyEditorSession(state, editorSession)
  applyWebPreferences(state, bootstrap.preferences || {})

  state.tasks.value = Array.isArray(taskSummary.items) ? taskSummary.items : []
  state.blocklyFiles.value = Array.isArray(bootstrap.blocklyFiles) ? bootstrap.blocklyFiles : []
  state.logs.value = []

  const activeTasks = Array.isArray(systemState.active_tasks) ? systemState.active_tasks : []
  if (!state.tasks.value.length && activeTasks.length) state.tasks.value = activeTasks

  state.sessions.value = normalizeConnectionList(deviceOverview.connection)
  state.emulatorDevices.value = normalizeDeviceItems(deviceOverview.emulator?.items)
  state.browserDevices.value = normalizeDeviceItems(deviceOverview.browser?.items)
  state.adbDevices.value = normalizeDeviceItems(deviceOverview.adb?.items)
  state.win32Windows.value = normalizeDesktopItems(deviceOverview.desktop?.items)

  if (state.selectedTaskId.value && !state.tasks.value.some(item => item.task_id === state.selectedTaskId.value)) {
    state.selectedTaskId.value = ''
  }
  if (!state.selectedTaskId.value && state.tasks.value.length) {
    state.selectedTaskId.value = state.tasks.value[state.tasks.value.length - 1].task_id
  }
  if (state.selectedSession.value && !state.sessions.value.some(item => item.label === state.selectedSession.value)) {
    state.selectedSession.value = ''
  }
  if (state.sessions.value.length && !state.selectedSession.value) {
    state.selectedSession.value = state.sessions.value[0].label
  }
  return editorHydration
}

