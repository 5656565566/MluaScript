import { authApi, deviceApi, editorApi, logApi, runApi, setUnauthorizedHandler, streamApi, systemApi, templateApi } from './api'
import {
  normalizeConnectionList,
  normalizeDesktopItems,
  normalizeDeviceItems,
} from './api/contracts'
import { createAppActions } from './app/appModule'
import { applyBootstrapState } from './app/bootstrap'
import { createUiState } from './app/uiState'
import { workspaceToLua, workspaceToXml, updateBlocklyTheme } from './blockly'
import { createDeviceActions } from './features/devices/deviceModule'
import { createDeviceState } from './features/devices/deviceState'
import { createEditorActions } from './features/editor/editorModule'
import { createEditorState } from './features/editor/editorState'
import { createRuntimeActions } from './features/runtime/runtimeModule'
import { createRuntimeState } from './features/runtime/runtimeState'
import { createRuntimeStreams } from './features/runtime/runtimeStreams'
import { createTemplateActions } from './features/templates/templateModule'
import { createTemplateState } from './features/templates/templateState'
import { openModal, closeModal } from './modalStore'
import { pickerActions } from './store/pickerState'
import { createGetters } from './store/getters'
import { createModalActions } from './ui/modalActions'

export const state = {
  ...createEditorState(),
  ...createDeviceState(),
  ...createRuntimeState(),
  ...createTemplateState(),
  ...createUiState(),
}

let runtimeActions
const runtimeStreams = createRuntimeStreams({
  streamApi,
  scheduler: window,
  isAuthenticated: () => state.authenticated.value,
  getSelectedTaskId: () => state.selectedTaskId.value,
  getLogParams: () => state.logOrigin.value ? { channel: state.logOrigin.value } : {},
  onLogsSnapshot: (items) => {
    state.logs.value = items
  },
  onLog: (payload, limit) => {
    state.logs.value = [...state.logs.value, payload].slice(-limit)
  },
  onTaskLogs: (...args) => runtimeActions.applyTaskLogs(...args),
  onTaskOutput: (...args) => runtimeActions.applyTaskOutput(...args),
})

export const getters = createGetters(state)

const applyBootstrap = (bootstrap) => applyBootstrapState({
  state,
  bootstrap,
  normalizeConnectionList,
  normalizeDesktopItems,
  normalizeDeviceItems,
})

const deviceActions = createDeviceActions({
  state,
  deviceApi,
  normalizeConnectionList,
  normalizeDesktopItems,
  normalizeDeviceItems,
  scheduler: window,
  getActions: () => actions,
})

const editorActions = createEditorActions({
  state,
  editorApi,
  workspaceToLua,
  workspaceToXml,
  scheduler: window,
  getActions: () => actions,
})

const templateActions = createTemplateActions({
  state,
  templateApi,
  getActions: () => actions,
})

const modalActions = createModalActions({
  state,
  openModal,
  getActions: () => actions,
})

const appActions = createAppActions({
  state,
  authApi,
  editorApi,
  logApi,
  systemApi,
  applyBootstrap,
  updateBlocklyTheme,
  browserWindow: window,
  browserDocument: document,
  getActions: () => actions,
})

runtimeActions = createRuntimeActions({
  state,
  systemApi,
  runApi,
  runtimeStreams,
  getActions: () => actions,
})

export const actions = {
  ...appActions,
  ...deviceActions,
  ...editorActions,
  ...modalActions,
  ...runtimeActions,
  ...templateActions,
  openBlocklyPicker(config = {}) {
    return pickerActions.open(config)
  },

  closeBlocklyPicker() {
    pickerActions.close()
  },

  closeModal,
  pickerActions,
}

setUnauthorizedHandler(() => actions.handleUnauthorized())
