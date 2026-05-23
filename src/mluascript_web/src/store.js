import { computed } from 'vue'
import { apiGet, apiPost, authApi, editorApi, logApi, streamApi, systemApi, templateApi } from './api'
import { workspaceToLua, workspaceToXml, updateBlocklyTheme } from './blockly'
import { openModal, closeModal } from './modalStore'
import { pickerActions } from './store/pickerState'
import CropModal from './components/CropModal.vue'
import SharedVariableManagerModal from './components/SharedVariableManagerModal.vue'
import BlocklyWorkspaceManagerModal from './components/BlocklyWorkspaceManagerModal.vue'
import TaskDetailModal from './components/TaskDetailModal.vue'
import TaskTraceModal from './components/TaskTraceModal.vue'
import { createDeviceState } from './store/deviceState'
import { createEditorState } from './store/editorState'
import { createRuntimeState } from './store/runtimeState'
import { createTemplateState } from './store/templateState'
import { createUiState } from './store/uiState'

export const state = {
  ...createEditorState(),
  ...createDeviceState(),
  ...createRuntimeState(),
  ...createTemplateState(),
  ...createUiState(),
}

const devicePreviewTimers = new Map()
let runtimeLogsStream = null
let runtimeLogsReconnectTimer = null
let selectedTaskLogsStream = null
let selectedTaskOutputStream = null
let selectedTaskStreamsTaskId = ''
let selectedTaskReconnectTimer = null

function closeEventSource(source) {
  if (source) source.close()
}

function scheduleReconnect(kind, factory) {
  const timerRef = kind === 'runtime' ? runtimeLogsReconnectTimer : selectedTaskReconnectTimer
  if (timerRef) return
  const timer = window.setTimeout(() => {
    if (kind === 'runtime') runtimeLogsReconnectTimer = null
    else selectedTaskReconnectTimer = null
    factory()
  }, 2000)
  if (kind === 'runtime') runtimeLogsReconnectTimer = timer
  else selectedTaskReconnectTimer = timer
}

function applyTaskLogsSnapshot(taskId, payload) {
  state.taskLogsById.value = {
    ...state.taskLogsById.value,
    [taskId]: payload,
  }
}

function applyTaskOutputSnapshot(taskId, payload) {
  state.taskOutputById.value = {
    ...state.taskOutputById.value,
    [taskId]: payload,
  }
}

export const getters = {
  imageUrl: computed(() => state.screenshotBase64.value ? `data:image/png;base64,${state.screenshotBase64.value}` : ''),
  pipelineTasks: computed(() => state.tasks.value.filter((item) => item.type === 'maa')),
  luaScriptFiles: computed(() => state.luaFiles.value.map((item) => ({
    ...item,
    name: item.name || item.filename || item.path,
  }))),
  filteredTaskManagerTasks: computed(() => {
    const keyword = state.taskManagerQuery.value.trim().toLowerCase()
    if (!keyword) return state.tasks.value
    return state.tasks.value.filter((item) => {
      const title = item.title || item.name || item.metadata?.entry || item.metadata?.script_path || ''
      const haystack = [
        title,
        item.task_id,
        item.kind,
        item.status,
        item.target,
        item.name,
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(keyword)
    })
  }),
  filteredBlocklyFiles: computed(() => {
    const keyword = state.blocklyManagerQuery.value.trim().toLowerCase()
    if (!keyword) return state.blocklyFiles.value
    return state.blocklyFiles.value.filter((item) => item.name.toLowerCase().includes(keyword))
  }),
  selectedTask: computed(() => {
    if (!state.selectedTaskId.value) return null
    return state.tasks.value.find((item) => item.task_id === state.selectedTaskId.value) || null
  }),
  selectedTaskDetail: computed(() => {
    if (!state.selectedTaskId.value) return null
    return state.taskDetailById.value[state.selectedTaskId.value] || null
  }),
  logCount: computed(() => state.logs.value.length),
  editorPaneClass: computed(() => `editor-pane layout-${state.editorLayout.value}`),
}

function cloneValue(value) {
  if (Array.isArray(value)) {
    return value.map(item => cloneValue(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneValue(item)]))
  }
  return value
}

function fieldKey(field) {
  return field?.key || field?.k || ''
}

function fieldType(field) {
  const type = field?.type || field?.tp || 'str'
  if (type === 'string') return 'str'
  if (type === 'number') return 'num'
  if (type === 'boolean') return 'bool'
  if (type === 'select') return 'enum'
  return type
}

function fieldDefaultValue(field) {
  if (Object.prototype.hasOwnProperty.call(field || {}, 'default')) return cloneValue(field.default)
  if (Object.prototype.hasOwnProperty.call(field || {}, 'def')) return cloneValue(field.def)
  if (fieldType(field) === 'bool') return false
  return ''
}

function normalizeRuntimeValue(field, value) {
  const type = fieldType(field)
  if (type === 'int' || type === 'num') {
    if (value === '' || value === null || typeof value === 'undefined') return ''
    const num = Number(value)
    if (Number.isNaN(num)) return ''
    return type === 'int' ? Math.trunc(num) : num
  }
  if (type === 'bool') return Boolean(value)
  if (type === 'json' || type === 'obj' || type === 'list') {
    if (typeof value !== 'string') return cloneValue(value)
    const text = value.trim()
    if (!text) return type === 'list' ? [] : ''
    try {
      return JSON.parse(text)
    } catch {
      return value
    }
  }
  return value
}

function normalizeTemplateField(field, key = '') {
  const normalizedKey = key || fieldKey(field)
  const type = fieldType(field)
  const rawCondition = field?.if || null
  const normalizedCondition = rawCondition
    ? {
        ...rawCondition,
        in: Array.isArray(rawCondition.in) ? rawCondition.in : [],
      }
    : null
  return {
    ...field,
    key: normalizedKey,
    label: field?.label || field?.t || normalizedKey,
    description: field?.description || field?.d || field?.note || '',
    type: type === 'str' ? 'string' : type === 'bool' ? 'boolean' : type === 'enum' ? 'select' : type === 'num' || type === 'int' ? 'number' : type,
    default: fieldDefaultValue(field),
    options: Array.isArray(field?.options) ? field.options : Array.isArray(field?.oneOf) ? field.oneOf.map(option => ({
      value: option?.value ?? option?.v ?? option,
      label: option?.label || option?.t || String(option?.value ?? option?.v ?? option),
    })) : [],
    rawType: type,
    if: normalizedCondition,
    grp: field?.grp || '',
    as: field?.as || '',
  }
}

function normalizeTemplateMetaForFrontend(meta) {
  if (!meta) return null
  const vars = meta.vars || {}
  const normalizedVars = Object.fromEntries(Object.entries(vars).map(([key, field]) => [key, normalizeTemplateField(field, key)]))
  const tasks = Array.isArray(meta.tasks) ? meta.tasks : Array.isArray(meta.taskCatalog) ? meta.taskCatalog : []
  const taskMap = Object.fromEntries(tasks.map(task => [task.k || task.key, task]))
  const workflows = (Array.isArray(meta.flows) ? meta.flows : Array.isArray(meta.workflows) ? meta.workflows : []).map((flow) => {
    const workflowKey = flow.k || flow.key || ''
    const globals = (flow.g || flow.globals || []).map(key => normalizedVars[key]).filter(Boolean)
    const steps = (flow.steps || flow.tasks || []).map((step) => {
      const taskRef = step.task || step.taskRef || ''
      const taskDef = taskMap[taskRef] || {}
      const argKeys = Array.isArray(taskDef.args) ? taskDef.args : []
      return {
        ...step,
        key: step.k || step.key || '',
        title: step.t || step.title || taskDef.t || taskDef.title || taskRef,
        description: step.d || step.description || taskDef.d || taskDef.description || '',
        userTitle: step.ut || step.userTitle || step.t || step.title || taskDef.ut || taskDef.userTitle || taskDef.t || taskDef.title || taskRef,
        userDescription: step.ud || step.userDescription || step.d || step.description || taskDef.ud || taskDef.userDescription || taskDef.d || taskDef.description || '',
        taskRef,
        functionRef: taskDef.fn || taskDef.functionRef || '',
        args: step.args || {},
        enabled: step.enabled ?? true,
        onFail: step.onFail || 'stop',
        allowDisable: step.allowDisable !== false,
        allowReorder: step.allowReorder !== false,
        fields: argKeys.map(key => normalizedVars[key]).filter(Boolean),
        _taskArgKeys: argKeys,
      }
    })
    return {
      ...flow,
      key: workflowKey,
      title: flow.t || flow.title || workflowKey,
      description: flow.d || flow.description || '',
      userTitle: flow.ut || flow.userTitle || flow.t || flow.title || workflowKey,
      userDescription: flow.ud || flow.userDescription || flow.d || flow.description || '',
      globals,
      tasks: steps,
    }
  })
  return {
    ...meta,
    title: meta.t || meta.title || meta.id || '',
    description: meta.d || meta.description || '',
    userTitle: meta.ut || meta.userTitle || meta.t || meta.title || '',
    userDescription: meta.ud || meta.userDescription || meta.d || meta.description || '',
    type: workflows.length ? 'workflow-template' : 'task-template',
    vars: normalizedVars,
    tasks,
    workflows,
    entry: {
      ...(meta.entry || {}),
      defaultWorkflow: meta.entry?.defaultWorkflow || meta.entry?.flow || workflows[0]?.key || '',
    },
  }
}

function buildTaskDefaults(meta, savedConfig) {
  const next = {}
  for (const task of meta?.tasks || []) {
    const taskKey = task.k || task.key
    next[taskKey] = { ...(savedConfig?.tasks?.[taskKey]?.params || {}) }
  }
  return next
}

function buildWorkflowDefaults(meta, savedConfig) {
  const workflows = meta?.workflows || []
  const next = {}
  for (const workflow of workflows) {
    const workflowKey = workflow.key
    const savedWorkflow = savedConfig?.flows?.[workflowKey] || savedConfig?.workflows?.[workflowKey] || {}
    const savedStepArgs = savedWorkflow.stepArgs || {}
    const savedStepEnabled = savedWorkflow.stepEnabled || {}
    const savedStepOrder = Array.isArray(savedWorkflow.stepOrder) ? savedWorkflow.stepOrder : []
    const savedGlobals = savedWorkflow.globals || {}
    const tasks = workflow.tasks || []
    next[workflowKey] = {
      stepOrder: savedStepOrder.length ? savedStepOrder.filter(key => tasks.some(step => step.key === key)).concat(tasks.map(step => step.key).filter(key => !savedStepOrder.includes(key))) : tasks.map(step => step.key),
      stepEnabled: Object.fromEntries(tasks.map(step => [step.key, Object.prototype.hasOwnProperty.call(savedStepEnabled, step.key) ? Boolean(savedStepEnabled[step.key]) : Boolean(step.enabled ?? true)])),
      stepArgs: Object.fromEntries(tasks.map(step => {
        const defaults = Object.fromEntries((step.fields || []).map(field => [field.key, fieldDefaultValue(field)]))
        return [step.key, { ...defaults, ...(step.args || {}), ...(savedStepArgs[step.key] || {}) }]
      })),
      globals: Object.fromEntries((workflow.globals || []).map(field => [field.key, Object.prototype.hasOwnProperty.call(savedGlobals, field.key) ? cloneValue(savedGlobals[field.key]) : fieldDefaultValue(field)])),
    }
  }
  return next
}

function applyEditorSession(editorSession = {}) {
  const blocklyDocument = editorSession.blocklyDocument || {}
  const luaDocument = editorSession.luaDocument || {}

  state.blocklyXml.value = String(blocklyDocument.xml || '')
  state.luaCode.value = String(luaDocument.content || '')
  state.lastSavedBlocklyXml.value = String(blocklyDocument.xml || '')

  state.blocklyFilename.value = String(blocklyDocument.filename || state.blocklyFilename.value || 'blockly.xml')
  state.filename.value = String(luaDocument.filename || state.filename.value || 'script.lua')
  state.savePath.value = String(luaDocument.path || state.savePath.value || '')
  state.blocklySavePath.value = String(blocklyDocument.path || state.blocklySavePath.value || '')
  state.blocklyDocumentMtime.value = blocklyDocument.mtime ?? null
  state.luaDocumentMtime.value = luaDocument.mtime ?? null
  state.blocklySaveMode.value = String(blocklyDocument.saveMode || state.blocklySaveMode.value || 'create')
  state.luaSaveMode.value = String(luaDocument.saveMode || state.luaSaveMode.value || 'create')
}

function applyBootstrapState(bootstrap = {}) {
  const systemState = bootstrap.systemState || {}
  const editorSession = bootstrap.editorSession || {}
  const deviceOverview = bootstrap.deviceOverview || {}
  const taskSummary = bootstrap.taskSummary || {}

  applyEditorSession(editorSession)

  state.tasks.value = Array.isArray(taskSummary.items) ? taskSummary.items : []
  state.blocklyFiles.value = Array.isArray(bootstrap.blocklyFiles) ? bootstrap.blocklyFiles : []
  state.logs.value = []

  const activeTasks = Array.isArray(systemState.active_tasks) ? systemState.active_tasks : []
  if (!state.tasks.value.length && activeTasks.length) {
    state.tasks.value = activeTasks
  }

  const connection = deviceOverview.connection || {}
  state.sessions.value = connection.label
    ? [{
      label: connection.label,
      connected: Boolean(connection.connected),
      canScreencap: Boolean(connection.can_screencap),
    }]
    : []

  state.emulatorDevices.value = Array.isArray(deviceOverview.emulator?.items)
    ? deviceOverview.emulator.items.map((item) => ({
      name: item.title,
      address: item.subtitle || '',
      id: item.id,
      tags: item.tags || [],
    }))
    : []

  state.browserDevices.value = Array.isArray(deviceOverview.browser?.items)
    ? deviceOverview.browser.items.map((item) => ({
      name: item.title,
      address: item.subtitle || '',
      id: item.id,
      tags: item.tags || [],
    }))
    : []

  state.adbDevices.value = Array.isArray(deviceOverview.adb?.items)
    ? deviceOverview.adb.items.map((item) => ({
      name: item.title,
      address: item.subtitle || '',
      id: item.id,
      tags: item.tags || [],
    }))
    : []

  state.win32Windows.value = Array.isArray(deviceOverview.desktop?.items)
    ? deviceOverview.desktop.items.map((item) => ({
      window_name: item.title,
      hwnd: item.handle || item.subtitle || '',
      handle: item.handle || item.subtitle || '',
      id: item.id,
      subtitle: item.subtitle || '',
    }))
    : []

  if (state.selectedTaskId.value && !state.tasks.value.some(item => item.task_id === state.selectedTaskId.value)) {
    state.selectedTaskId.value = ''
  }
  if (!state.selectedTaskId.value && state.tasks.value.length) {
    state.selectedTaskId.value = state.tasks.value[state.tasks.value.length - 1].task_id
  }

  if (state.selectedSession.value && !state.sessions.value.some((item) => item.label === state.selectedSession.value)) {
    state.selectedSession.value = ''
  }
  if (state.sessions.value.length && !state.selectedSession.value) {
    state.selectedSession.value = state.sessions.value[0].label
  }
}

function markFeatureUnavailable(name) {
  throw new Error(`${name} 暂未实现`)
}

function getTemplateSelectedFlowKey(meta, savedConfig) {
  const defaultFlow = meta?.entry?.defaultWorkflow || meta?.entry?.flow || meta?.workflows?.[0]?.key || ''
  return savedConfig?.selectedFlowKey || defaultFlow
}

function ensureTemplateWorkflowState(meta, savedConfig) {
  const workflowDefaults = buildWorkflowDefaults(meta, savedConfig)
  const selectedFlowKey = getTemplateSelectedFlowKey(meta, savedConfig)
  state.selectedTemplateMeta.value = meta
  state.templateScriptType.value = 'workflow-template'
  state.selectedWorkflowKey.value = selectedFlowKey
  state.templateWorkflowFormData.value = workflowDefaults
}

function ensureTemplateTaskState(meta, savedConfig) {
  state.selectedTemplateMeta.value = meta
  state.templateScriptType.value = 'task-template'
  state.selectedWorkflowKey.value = ''
  state.templateTaskFormData.value = buildTaskDefaults(meta, savedConfig)
  state.templateWorkflowFormData.value = {}
}

function normalizeTemplateSavedConfig(savedConfig) {
  if (!savedConfig || typeof savedConfig !== 'object') return {}
  return {
    ...savedConfig,
    flows: savedConfig.flows || savedConfig.workflows || {},
    tasks: savedConfig.tasks || {},
  }
}

function createPreviewWindow(sessionLabel) {
  const offset = state.nextPreviewWindowOffset.value || 0
  state.nextPreviewWindowOffset.value = offset + 1
  return {
    id: `${sessionLabel}-${Date.now()}-${offset}`,
    label: sessionLabel,
    imageBase64: '',
    intervalMs: Number(state.devicePreviewIntervalMs.value) || 1000,
    x: 24 + (offset % 4) * 32,
    y: 96 + (offset % 4) * 24,
  }
}

async function syncSelectedTaskRuntimeData() {
  const selectedTaskId = state.selectedTaskId.value
  if (!selectedTaskId) return null
  return await actions.fetchTaskDetail(selectedTaskId)
}

async function refreshRuntimeSummary() {
  const [tasksPayload, scriptsPayload] = await Promise.all([
    apiGet('/api/system/tasks'),
    systemApi.listScripts(),
  ])
  state.tasks.value = tasksPayload.items || tasksPayload.data?.items || []
  state.availableScripts.value = scriptsPayload.items || []
  if (state.selectedTaskId.value && !state.tasks.value.some(item => item.task_id === state.selectedTaskId.value)) {
    actions.stopSelectedTaskStreams()
    state.selectedTaskId.value = ''
  }
  if (!state.selectedTaskId.value && state.tasks.value.length) {
    state.selectedTaskId.value = state.tasks.value[state.tasks.value.length - 1].task_id
  }
  return await syncSelectedTaskRuntimeData()
}

export const actions = {
  async checkAuth() {
    const data = await authApi.status()
    state.authenticated.value = Boolean(data.authenticated)
    state.currentUser.value = data.username || ''
    state.authChecked.value = true
    return state.authenticated.value
  },

  async login(username, password) {
    const data = await authApi.login({ username, password })
    state.authenticated.value = Boolean(data.authenticated)
    state.currentUser.value = data.username || username
    state.authChecked.value = true
    actions.setStatus('登录成功', 'success')
  },

  async logout() {
    await authApi.logout()
    state.authenticated.value = false
    state.currentUser.value = ''
    actions.stopRuntimeStreams()
    actions.stopSelectedTaskStreams()
    actions.stopAllDevicePreviewLoops()
    state.tasks.value = []
    state.logs.value = []
    actions.setStatus('已退出登录', 'info')
  },

  setStatus(text, type = 'info') {
    state.statusText.value = text
    const messageApi = window.$message
    if (!messageApi) return
    if (type === 'error') messageApi.error(text)
    else if (type === 'success') messageApi.success(text)
    else if (type === 'warning') messageApi.warning(text)
    else messageApi.info(text)
  },

  async handleAction(handler) {
    if (state.loading.value) return
    state.loading.value = true
    try {
      await handler()
    } catch (error) {
      console.error(error)
      actions.setStatus(error.message || '操作失败', 'error')
    } finally {
      state.loading.value = false
    }
  },

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.()
    } else {
      document.exitFullscreen?.()
    }
  },

  openBlocklyPicker(config = {}) {
    return pickerActions.open(config)
  },

  closeBlocklyPicker() {
    pickerActions.close()
  },

  async openSharedVariableManager() {
    return openModal({
      type: 'shared-variable-manager',
      component: SharedVariableManagerModal,
      props: {},
      options: {
        title: '共享变量管理',
        size: 'lg',
      },
    })
  },

  async openBlocklyWorkspaceManager() {
    return openModal({
      type: 'blockly-workspace-manager',
      component: BlocklyWorkspaceManagerModal,
      props: {},
      options: {
        title: 'Blockly 工作区管理',
        size: 'xl',
      },
    })
  },

  async fetchTaskDetail(taskId) {
    if (!taskId) return null
    const data = await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}`)
    state.taskDetailById.value = {
      ...state.taskDetailById.value,
      [taskId]: data.data || data,
    }
    return state.taskDetailById.value[taskId]
  },

  async fetchTaskLogs(taskId) {
    if (!taskId) return null
    const data = await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}/logs`)
    applyTaskLogsSnapshot(taskId, data.data || data)
    return state.taskLogsById.value[taskId]
  },

  async fetchTaskOutput(taskId) {
    if (!taskId) return null
    const data = await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}/output`)
    applyTaskOutputSnapshot(taskId, data.data || data)
    return state.taskOutputById.value[taskId]
  },

  stopRuntimeStreams() {
    closeEventSource(runtimeLogsStream)
    runtimeLogsStream = null
    if (runtimeLogsReconnectTimer) {
      window.clearTimeout(runtimeLogsReconnectTimer)
      runtimeLogsReconnectTimer = null
    }
  },

  startRuntimeStreams() {
    actions.stopRuntimeStreams()
    if (!state.authenticated.value) return
    const source = streamApi.createLogsStream(state.logOrigin.value ? { channel: state.logOrigin.value } : {})
    runtimeLogsStream = source
    source.addEventListener('snapshot', (event) => {
      const payload = JSON.parse(event.data || '{}')
      state.logs.value = Array.isArray(payload.items) ? payload.items : []
    })
    source.addEventListener('log', (event) => {
      const payload = JSON.parse(event.data || '{}')
      state.logs.value = [...state.logs.value, payload]
    })
    source.addEventListener('heartbeat', () => {})
    source.onerror = () => {
      if (runtimeLogsStream !== source) return
      closeEventSource(source)
      runtimeLogsStream = null
      scheduleReconnect('runtime', () => actions.startRuntimeStreams())
    }
  },

  stopSelectedTaskStreams() {
    closeEventSource(selectedTaskLogsStream)
    closeEventSource(selectedTaskOutputStream)
    selectedTaskLogsStream = null
    selectedTaskOutputStream = null
    selectedTaskStreamsTaskId = ''
    if (selectedTaskReconnectTimer) {
      window.clearTimeout(selectedTaskReconnectTimer)
      selectedTaskReconnectTimer = null
    }
  },

  startSelectedTaskStreams(taskId = state.selectedTaskId.value) {
    if (!taskId) {
      actions.stopSelectedTaskStreams()
      return
    }
    if (selectedTaskStreamsTaskId === taskId && selectedTaskLogsStream && selectedTaskOutputStream) return

    actions.stopSelectedTaskStreams()
    selectedTaskStreamsTaskId = taskId

    const ensureCurrentTask = () => state.selectedTaskId.value === taskId && selectedTaskStreamsTaskId === taskId
    const reconnect = () => {
      if (!ensureCurrentTask()) return
      scheduleReconnect('task', () => actions.startSelectedTaskStreams(taskId))
    }

    const logsSource = streamApi.createTaskLogsStream(taskId)
    selectedTaskLogsStream = logsSource
    logsSource.addEventListener('snapshot', (event) => {
      if (!ensureCurrentTask()) return
      applyTaskLogsSnapshot(taskId, JSON.parse(event.data || '{}'))
    })
    logsSource.addEventListener('update', (event) => {
      if (!ensureCurrentTask()) return
      applyTaskLogsSnapshot(taskId, JSON.parse(event.data || '{}'))
    })
    logsSource.addEventListener('not_found', () => {
      if (!ensureCurrentTask()) return
      actions.stopSelectedTaskStreams()
    })
    logsSource.addEventListener('heartbeat', () => {})
    logsSource.onerror = () => {
      if (selectedTaskLogsStream !== logsSource) return
      closeEventSource(logsSource)
      selectedTaskLogsStream = null
      reconnect()
    }

    const outputSource = streamApi.createTaskOutputStream(taskId)
    selectedTaskOutputStream = outputSource
    outputSource.addEventListener('snapshot', (event) => {
      if (!ensureCurrentTask()) return
      applyTaskOutputSnapshot(taskId, JSON.parse(event.data || '{}'))
    })
    outputSource.addEventListener('update', (event) => {
      if (!ensureCurrentTask()) return
      applyTaskOutputSnapshot(taskId, JSON.parse(event.data || '{}'))
    })
    outputSource.addEventListener('not_found', () => {
      if (!ensureCurrentTask()) return
      actions.stopSelectedTaskStreams()
    })
    outputSource.addEventListener('heartbeat', () => {})
    outputSource.onerror = () => {
      if (selectedTaskOutputStream !== outputSource) return
      closeEventSource(outputSource)
      selectedTaskOutputStream = null
      reconnect()
    }
  },

  async removeTask(taskId) {
    if (!taskId) return
    await systemApi.removeTask(taskId)
    if (state.selectedTaskId.value === taskId) {
      state.selectedTaskId.value = ''
    }
    await actions.loadState()
  },

  async stopTask(taskId, kind = 'script') {
    if (!taskId) return
    await apiPost(`/api/run/${kind}/${encodeURIComponent(taskId)}/stop`, {})
    await actions.loadState()
  },

  async refreshTaskManagerData() {
    const detail = await refreshRuntimeSummary()
    return { detail: detail || null }
  },

  async openTaskDetailModal(taskId) {
    if (!taskId) return null
    state.selectedTaskId.value = taskId
    await actions.fetchTaskDetail(taskId)
    actions.startSelectedTaskStreams(taskId)
    return openModal({
      type: 'task-detail',
      component: TaskDetailModal,
      props: { taskId },
      options: {
        title: '任务详情',
        size: 'xl',
        panelClass: 'task-detail-modal-panel',
        contentClass: 'task-detail-modal-content',
      },
    })
  },

  async openTaskLogsModal(taskId) {
    if (!taskId) return null
    state.selectedTaskId.value = taskId
    await Promise.all([
      actions.fetchTaskDetail(taskId),
      actions.fetchTaskLogs(taskId),
    ])
    actions.startSelectedTaskStreams(taskId)
    return openModal({
      type: 'task-logs',
      component: TaskTraceModal,
      props: { taskId, mode: 'logs' },
      options: {
        title: '任务日志',
        size: 'xl',
        panelClass: 'task-logs-modal-panel',
        contentClass: 'task-logs-modal-content',
      },
    })
  },

  async openTaskOutputModal(taskId) {
    if (!taskId) return null
    state.selectedTaskId.value = taskId
    await Promise.all([
      actions.fetchTaskDetail(taskId),
      actions.fetchTaskOutput(taskId),
    ])
    actions.startSelectedTaskStreams(taskId)
    return openModal({
      type: 'task-output',
      component: TaskTraceModal,
      props: { taskId, mode: 'output' },
      options: {
        title: '任务输出',
        size: 'xl',
        panelClass: 'task-output-modal-panel',
        contentClass: 'task-output-modal-content',
      },
    })
  },

  rebuildLuaCode() {
    if (!state.blocklyEditor.value) return
    state.blocklyXml.value = workspaceToXml(state.blocklyEditor.value)
    state.luaCode.value = workspaceToLua(state.blocklyEditor.value)
  },

  placeScreenshotDock() {
    state.screenshotPosition.value = {
      x: Math.max(16, window.innerWidth - 360),
      y: 96,
    }
  },

  async syncWorkspace() {
    if (!state.blocklyEditor.value) return
    actions.rebuildLuaCode()
    await editorApi.syncSession({
      blocklyDocument: {
        xml: state.blocklyXml.value,
        filename: state.blocklyFilename.value,
        path: state.blocklySavePath.value,
      },
      luaDocument: {
        content: state.luaCode.value,
        filename: state.filename.value,
        path: state.savePath.value,
      },
    })
  },

  async loadState() {
    const [bootstrap, logData, luaFilesPayload, tasksPayload, scriptsPayload] = await Promise.all([
      systemApi.getBootstrap(),
      logApi.list(state.logOrigin.value ? { channel: state.logOrigin.value } : {}),
      editorApi.listLuaFiles(),
      apiGet('/api/system/tasks'),
      systemApi.listScripts(),
    ])

    applyBootstrapState(bootstrap)
    state.logs.value = logData.items || []
    state.luaFiles.value = luaFilesPayload.items || []
    state.tasks.value = tasksPayload.items || []
    state.availableScripts.value = scriptsPayload.items || []
    await syncSelectedTaskRuntimeData()
    actions.startRuntimeStreams()
    actions.startSelectedTaskStreams()
  },

  async refreshLogs(logOrigin = state.logOrigin.value) {
    state.logOrigin.value = logOrigin
    actions.startRuntimeStreams()
  },

  async pollRuntime() {
    if (!state.autoRefresh.value) return
    try {
      await refreshRuntimeSummary()
    } catch (error) {
      console.error(error)
    }
  },

  async initFramework() {
    markFeatureUnavailable('MaaFramework 初始化')
  },

  applyTheme(themeValue = state.appTheme.value) {
    state.appTheme.value = themeValue
    const isDark = themeValue === 'dark' || (themeValue === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
    document.documentElement.style.colorScheme = isDark ? 'dark' : 'light'

    if (state.blocklyEditor.value) {
      updateBlocklyTheme(state.blocklyEditor.value, isDark)
    }

    window.dispatchEvent(new Event('resize'))
  },

  async searchAdb() {
    const data = await apiPost('/api/device/discover', { kind: 'adb' })
    state.adbDevices.value = (data.items || []).filter((item) => String(item.id || '').startsWith('adb:'))
    actions.setStatus(data.message || `搜索到 ${state.adbDevices.value.length} 个 ADB 设备`)
  },

  async connectAdb(address = state.adbAddress.value) {
    const result = await apiPost('/api/device/adb/connect-manual', { address })
    const connection = result.connection || {}
    state.sessions.value = connection.label ? [connection] : []
    state.selectedSession.value = connection.label || ''
    actions.setStatus(result.message || `ADB 已连接: ${connection.label || address}`, 'success')
  },

  async loadEmulators() {
    state.emulatorDevices.value = (await apiGet('/api/device/items', { kind: 'emulator' })).items || []
    actions.setStatus(`已加载 ${state.emulatorDevices.value.length} 个模拟器配置`)
  },

  async loadBrowsers() {
    state.browserDevices.value = (await apiGet('/api/device/items', { kind: 'browser' })).items || []
    actions.setStatus(`已加载 ${state.browserDevices.value.length} 个浏览器配置`)
  },

  async connectEmulator(deviceRef) {
    const device = state.emulatorDevices.value.find((item) => item.id === deviceRef || String(item.address || '') === String(deviceRef))
    if (!device?.id) throw new Error('未找到对应模拟器设备')
    const result = await apiPost('/api/device/connect', { deviceId: device.id })
    const connection = result.connection || {}
    state.sessions.value = connection.label ? [connection] : []
    state.selectedSession.value = connection.label || ''
    actions.setStatus(result.message || `模拟器已连接: ${connection.label || device.address || deviceRef}`, 'success')
  },

  async connectBrowser(deviceId) {
    if (!deviceId) throw new Error('未找到对应浏览器设备')
    const result = await apiPost('/api/device/connect', { deviceId })
    const connection = result.connection || {}
    state.sessions.value = connection.label ? [connection] : []
    state.selectedSession.value = connection.label || ''
    actions.setStatus(result.message || `浏览器已连接: ${connection.label || deviceId}`, 'success')
  },

  async searchWin32() {
    const data = await apiPost('/api/device/discover', { kind: 'desktop' })
    const items = Array.isArray(data?.items) ? data.items : []
    state.win32Windows.value = items
      .filter((item) => String(item.id || '').startsWith('desktop:'))
      .map((item) => ({
        window_name: item.title || item.window_name || '未命名窗口',
        hwnd: item.hwnd || item.handle || item.subtitle || '',
        handle: item.handle || item.hwnd || item.subtitle || '',
        id: item.id,
        subtitle: item.subtitle || '',
      }))
    actions.setStatus(data.message || `搜索到 ${state.win32Windows.value.length} 个本地窗口`)
  },

  async connectWin32(hwnd) {
    const normalizedHwnd = String(hwnd || '').trim()
    const device = state.win32Windows.value.find((item) => {
      const candidates = [
        item.id,
        item.hwnd,
        item.handle,
        item.subtitle,
      ].filter(Boolean).map((value) => String(value))
      return candidates.some((value) => value === normalizedHwnd || value.includes(normalizedHwnd))
    })
    if (!device?.id) throw new Error('未找到对应本地窗口')
    const result = await apiPost('/api/device/connect', { deviceId: device.id })
    const connection = result.connection || {}
    state.sessions.value = connection.label ? [connection] : []
    state.selectedSession.value = connection.label || ''
    actions.setStatus(result.message || `本地窗口已连接: ${connection.label || hwnd}`, 'success')
  },

  async reloadSessions() {
    const data = await apiGet('/api/device/session')
    const item = data.item || {}
    state.sessions.value = item.label ? [item] : []
    if (state.selectedSession.value && !state.sessions.value.some((session) => session.label === state.selectedSession.value)) {
      state.selectedSession.value = ''
    }
    if (state.sessions.value.length && !state.selectedSession.value) {
      state.selectedSession.value = state.sessions.value[0].label
    }
  },

  async disconnectSession(label = state.selectedSession.value) {
    void label
    const data = await apiPost('/api/device/disconnect', {})
    state.sessions.value = data.sessions || []
    state.selectedSession.value = ''
    if (state.sessions.value.length) {
      state.selectedSession.value = state.sessions.value[0].label
    }
    actions.stopAllDevicePreviewLoops()
    state.devicePreviewWindows.value = []
    actions.setStatus(data.message || '设备已断开', 'success')
  },

  async doScreencap() {
    if (!state.selectedSession.value) throw new Error('请先选择一个连接的设备')
    const data = await apiPost('/api/device/screencap', {})
    actions.setStatus(data.message || '截图成功', 'success')
    if (data.imageBase64) {
      state.screenshotBase64.value = data.imageBase64
      state.showScreenshot.value = true
      state.screenshotPath.value = '截图时间：' + new Date().toLocaleTimeString()
    }
  },

  async captureDevicePreviewFrame(windowId, sessionLabel) {
    if (!windowId || !sessionLabel) return
    const data = await apiPost('/api/device/screencap', {})
    if (data.imageBase64) {
      state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) =>
        win.id === windowId ? { ...win, imageBase64: data.imageBase64 } : win
      )
    }
  },

  async startDevicePreviewLoop(windowId) {
    const win = state.devicePreviewWindows.value.find((item) => item.id === windowId)
    if (!win) return
    actions.stopDevicePreviewLoop(windowId)
    await actions.captureDevicePreviewFrame(win.id, win.label)
    const interval = Math.max(200, Number(win.intervalMs || state.devicePreviewIntervalMs.value) || 1000)
    const timer = window.setInterval(() => {
      actions.captureDevicePreviewFrame(win.id, win.label).catch((error) => console.error(error))
    }, interval)
    devicePreviewTimers.set(windowId, timer)
  },

  stopDevicePreviewLoop(windowId) {
    const timer = devicePreviewTimers.get(windowId)
    if (timer) {
      window.clearInterval(timer)
      devicePreviewTimers.delete(windowId)
    }
  },

  stopAllDevicePreviewLoops() {
    for (const [windowId, timer] of devicePreviewTimers.entries()) {
      window.clearInterval(timer)
      devicePreviewTimers.delete(windowId)
    }
  },

  async openDevicePreviewWindow() {
    if (!state.selectedSession.value) throw new Error('请先选择一个连接的设备')
    const win = createPreviewWindow(state.selectedSession.value)
    state.devicePreviewWindows.value = [...state.devicePreviewWindows.value, win]
    await actions.startDevicePreviewLoop(win.id)
  },

  closeDevicePreviewWindow(windowId) {
    actions.stopDevicePreviewLoop(windowId)
    state.devicePreviewWindows.value = state.devicePreviewWindows.value.filter((item) => item.id !== windowId)
  },

  updateDevicePreviewWindowPosition(windowId, x, y) {
    state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) =>
      win.id === windowId
        ? { ...win, x: Math.max(0, Math.round(x)), y: Math.max(0, Math.round(y)) }
        : win
    )
  },

  setDevicePreviewInterval(intervalMs) {
    const next = Number(intervalMs) || 1000
    state.devicePreviewIntervalMs.value = next
    state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) => ({
      ...win,
      intervalMs: next,
    }))
    state.devicePreviewWindows.value.forEach((win) => {
      actions.startDevicePreviewLoop(win.id).catch((error) => console.error(error))
    })
  },

  openCropModal() {
    return openModal({
      type: 'crop-modal',
      component: CropModal,
      props: {},
      options: {
        title: '截图编辑 (裁切)',
        size: 'xl',
        panelClass: 'crop-modal-panel',
        contentClass: 'crop-modal-content-wrap',
      },
    })
  },

  async saveCroppedImage(filename, imageBase64) {
    void filename
    void imageBase64
    markFeatureUnavailable('裁切图片保存')
  },

  async saveLuaScript() {
    actions.rebuildLuaCode()
    const currentFilename = state.filename.value || 'script.lua'
    const savedPathFilename = state.savePath.value ? state.savePath.value.split('/').pop() : ''
    const filenameChanged = state.luaSaveMode.value === 'update' && savedPathFilename && savedPathFilename !== currentFilename

    let effectiveSaveMode = state.luaSaveMode.value
    let effectivePath = state.savePath.value || currentFilename
    let effectiveMtime = state.luaDocumentMtime.value

    if (filenameChanged) {
      effectiveSaveMode = 'create'
      effectivePath = currentFilename
      effectiveMtime = null
    }

    const payload = {
      path: effectivePath,
      content: state.luaCode.value,
      expectedMtime: effectiveMtime,
    }
    const data = effectiveSaveMode === 'update'
      ? await editorApi.updateLuaFile(payload)
      : await editorApi.createLuaFile({ path: payload.path, content: payload.content })

    state.filename.value = data.filename || state.filename.value
    state.savePath.value = data.path || state.savePath.value
    state.luaDocumentMtime.value = data.mtime ?? null
    state.luaSaveMode.value = 'update'
    await actions.syncWorkspace()
    actions.setStatus(`Lua 文件已保存到 ${state.savePath.value}`, 'success')
  },

  async saveBlocklyWorkspace(showStatus = true) {
    actions.rebuildLuaCode()
    const currentFilename = state.blocklyFilename.value || 'blockly.xml'
    const savedPathFilename = state.blocklySavePath.value ? state.blocklySavePath.value.split('/').pop() : ''
    const filenameChanged = state.blocklySaveMode.value === 'update' && savedPathFilename && savedPathFilename !== currentFilename

    let effectiveSaveMode = state.blocklySaveMode.value
    let effectivePath = state.blocklySavePath.value || currentFilename
    let effectiveMtime = state.blocklyDocumentMtime.value

    if (filenameChanged) {
      effectiveSaveMode = 'create'
      effectivePath = currentFilename
      effectiveMtime = null
    }

    const payload = {
      path: effectivePath,
      xml: state.blocklyXml.value,
      expectedMtime: effectiveMtime,
    }
    const data = effectiveSaveMode === 'update'
      ? await editorApi.updateBlocklyFile(payload)
      : await editorApi.createBlocklyFile({ path: payload.path, xml: payload.xml })

    state.blocklyFilename.value = data.filename || state.blocklyFilename.value
    state.blocklySavePath.value = data.path || state.blocklySavePath.value
    state.blocklySaveDir.value = data.path || state.blocklySaveDir.value
    state.blocklyDocumentMtime.value = data.mtime ?? null
    state.blocklySaveMode.value = 'update'
    state.lastSavedBlocklyXml.value = state.blocklyXml.value
    await actions.syncWorkspace()
    if (showStatus) actions.setStatus(`Blockly 已保存到 ${state.blocklySavePath.value}`, 'success')
  },

  async loadBlocklyWorkspace(filename) {
    const data = await editorApi.loadBlocklyFile(filename)
    state.blocklyFilename.value = data.filename || filename
    state.blocklySavePath.value = data.path || filename
    state.blocklyXml.value = data.xml || ''
    state.blocklyDocumentMtime.value = data.mtime ?? null
    state.blocklySaveMode.value = data.saveMode || 'update'
    state.lastSavedBlocklyXml.value = state.blocklyXml.value
    actions.setStatus(`已加载 Blockly XML: ${state.blocklyFilename.value}`)
    if (state.blocklyEditor.value) {
      state.suppressBlocklyAutosave.value = true
      try {
        const { utils, Xml, Events } = await import('blockly')
        Events.disable()
        try {
          state.blocklyEditor.value.clear()
          if (state.blocklyXml.value) {
            const dom = utils.xml.textToDom(state.blocklyXml.value)
            Xml.domToWorkspace(dom, state.blocklyEditor.value)
          }
        } finally {
          Events.enable()
        }
        // 手动触发 FINISHED_LOADING 事件 使依赖 onChange 回调恢复显示标签的块
        // （如 template_arg_get、procedure_call_picker 等）能正确恢复
        const finishedEvent = new Events.FinishedLoading(state.blocklyEditor.value)
        Events.fire(finishedEvent)
        actions.rebuildLuaCode()
        await actions.syncWorkspace()
      } finally {
        window.setTimeout(() => {
          state.suppressBlocklyAutosave.value = false
        }, 100)
      }
    }
  },

  async createNewBlocklyWorkspace(path) {
    const data = await editorApi.createBlocklyFile({ path, xml: state.blocklyXml.value || '<xml xmlns="https://developers.google.com/blockly/xml"></xml>' })
    state.blocklyFilename.value = data.filename || state.blocklyFilename.value
    state.blocklySavePath.value = data.path || state.blocklySavePath.value
    state.blocklyDocumentMtime.value = data.mtime ?? null
    state.blocklySaveMode.value = 'update'
    state.lastSavedBlocklyXml.value = state.blocklyXml.value
    await actions.reloadBlocklyFiles()
    actions.setStatus(`已创建 Blockly 文件: ${state.blocklyFilename.value}`, 'success')
    return data
  },

  async validateBlocklyName(path) {
    return editorApi.validateBlocklyName(path)
  },

  async reloadBlocklyFiles() {
    const data = await editorApi.listBlocklyFiles()
    state.blocklyFiles.value = data.items || []
  },

  async loadLuaFile(path) {
    const data = await editorApi.loadLuaFile(path)
    state.filename.value = data.filename || path
    state.savePath.value = data.path || path
    state.luaCode.value = data.content || ''
    state.luaDocumentMtime.value = data.mtime ?? null
    state.luaSaveMode.value = data.saveMode || 'update'
    await actions.syncWorkspace()
    actions.setStatus(`已加载 Lua 文件: ${state.filename.value}`)
  },

  async createNewLuaFile(path) {
    actions.rebuildLuaCode()
    const data = await editorApi.createLuaFile({ path, content: state.luaCode.value })
    state.filename.value = data.filename || state.filename.value
    state.savePath.value = data.path || state.savePath.value
    state.luaDocumentMtime.value = data.mtime ?? null
    state.luaSaveMode.value = 'update'
    await actions.syncWorkspace()
    actions.setStatus(`已创建 Lua 文件: ${state.filename.value}`, 'success')
    return data
  },

  async validateLuaName(path) {
    return editorApi.validateLuaName(path)
  },

  async loadLuaFiles() {
    const data = await editorApi.listLuaFiles()
    state.luaFiles.value = data.items || []
  },

  async runLuaScript(scriptPath = null, luaCode = null, sessionLabel = state.selectedSession.value) {
    state.runtimeState.value = 'running-lua'
    const data = await apiPost('/api/run/lua', {
      sessionLabel: sessionLabel || null,
      luaCode: luaCode ?? state.luaCode.value ?? '',
      scriptPath: scriptPath || state.savePath.value || state.filename.value || null,
    })
    state.runtimeState.value = 'idle'
    await actions.loadState()
    actions.setStatus(data.message || 'Lua 任务已启动', 'success')
    return data
  },

  async runLuaTask(sessionLabel = state.selectedSession.value, luaCode = state.luaCode.value, scriptPath = state.savePath.value || state.filename.value) {
    return await actions.runLuaScript(scriptPath, luaCode, sessionLabel)
  },

  async stopLuaTask(taskId) {
    if (!taskId) throw new Error('缺少 taskId')
    await apiPost(`/api/run/script/${encodeURIComponent(taskId)}/stop`, {})
    await actions.loadState()
    actions.setStatus(`已停止任务: ${taskId}`, 'success')
  },

  async runPipelineTask(entry, override = {}, sessionLabel = state.selectedSession.value, projectPath = '') {
    void sessionLabel
    const data = await apiPost('/api/run/pipeline', { entry, override, projectPath })
    await actions.loadState()
    actions.setStatus(data.message || 'Pipeline 任务已启动', 'success')
    return data
  },

  async loadTemplate(scriptPath) {
    const data = await templateApi.getScriptTemplate(scriptPath)
    const payload = data.data || data
    if (!payload.hasTemplate) {
      state.selectedTemplateMeta.value = null
      state.selectedTemplateSavedConfig.value = {}
      state.selectedTemplateScript.value = scriptPath
      state.selectedTemplateConfigPath.value = ''
      state.templateScriptType.value = ''
      state.selectedWorkflowKey.value = ''
      state.templateTaskFormData.value = {}
      state.templateWorkflowFormData.value = {}
      return payload
    }

    const meta = normalizeTemplateMetaForFrontend(payload.meta)
    const savedConfig = normalizeTemplateSavedConfig(payload.savedConfig)
    state.selectedTemplateScript.value = {
      path: payload.scriptPath || scriptPath,
      name: payload.scriptName || String(payload.scriptPath || scriptPath).split('/').pop() || String(scriptPath).split('/').pop() || '模板脚本',
    }
    state.selectedTemplateConfigPath.value = payload.configPath || ''
    state.selectedTemplateSavedConfig.value = savedConfig

    if (meta?.type === 'workflow-template') ensureTemplateWorkflowState(meta, savedConfig)
    else ensureTemplateTaskState(meta, savedConfig)

    return payload
  },

  setTemplateSelectedFlow(key) {
    state.selectedWorkflowKey.value = key || ''
  },

  setTemplateCurrentStep(key) {
    state.selectedTaskKey.value = key || ''
  },

  updateTemplateTaskValue(taskKey, fieldKey, value) {
    state.templateTaskFormData.value = {
      ...state.templateTaskFormData.value,
      [taskKey]: {
        ...(state.templateTaskFormData.value[taskKey] || {}),
        [fieldKey]: value,
      },
    }
  },

  updateWorkflowGlobals(workflowKey, globals) {
    if (!workflowKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
    state.templateWorkflowFormData.value = {
      ...state.templateWorkflowFormData.value,
      [workflowKey]: {
        ...state.templateWorkflowFormData.value[workflowKey],
        globals: { ...(globals || {}) },
      },
    }
  },

  updateWorkflowStepArg(workflowKey, stepKey, fieldKey, value) {
    if (!workflowKey || !stepKey || !fieldKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
    const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
    state.templateWorkflowFormData.value = {
      ...state.templateWorkflowFormData.value,
      [workflowKey]: {
        ...currentWorkflow,
        stepArgs: {
          ...(currentWorkflow.stepArgs || {}),
          [stepKey]: {
            ...(currentWorkflow.stepArgs?.[stepKey] || {}),
            [fieldKey]: value,
          },
        },
      },
    }
  },

  updateWorkflowStepEnabled(workflowKey, stepKey, enabled) {
    if (!workflowKey || !stepKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
    const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
    state.templateWorkflowFormData.value = {
      ...state.templateWorkflowFormData.value,
      [workflowKey]: {
        ...currentWorkflow,
        stepEnabled: {
          ...(currentWorkflow.stepEnabled || {}),
          [stepKey]: Boolean(enabled),
        },
      },
    }
  },

  moveWorkflowStep(workflowKey, stepKey, direction) {
    if (!workflowKey || !stepKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
    const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
    const list = Array.isArray(currentWorkflow.stepOrder) ? [...currentWorkflow.stepOrder] : []
    const index = list.indexOf(stepKey)
    if (index < 0) return
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= list.length) return
    const [item] = list.splice(index, 1)
    list.splice(target, 0, item)
    state.templateWorkflowFormData.value = {
      ...state.templateWorkflowFormData.value,
      [workflowKey]: {
        ...currentWorkflow,
        stepOrder: list,
      },
    }
  },

  buildTemplateRunPayload() {
    const meta = state.selectedTemplateMeta.value
    if (!meta) throw new Error('当前没有模板元数据')
    const script = state.selectedTemplateScript.value
    const scriptPath = typeof script === 'string' ? script : script?.path
    if (!scriptPath) throw new Error('缺少模板脚本路径')
    if (meta.type === 'workflow-template') {
      const workflowKey = state.selectedWorkflowKey.value || meta.entry?.defaultWorkflow || meta.workflows?.[0]?.key || ''
      if (!workflowKey) throw new Error('缺少工作流选择')
      return {
        scriptPath,
        mode: 'workflow',
        workflowKey,
        workflow: state.templateWorkflowFormData.value?.[workflowKey] || {},
        runtime: {},
      }
    }
    return {
      scriptPath,
      mode: 'task',
      workflowKey: '',
      workflow: {},
      runtime: {
        tasks: state.templateTaskFormData.value,
      },
    }
  },

  async runTemplateWorkflow() {
    const payload = actions.buildTemplateRunPayload()
    const data = await templateApi.runWorkflow(payload)
    await actions.loadState()
    actions.setStatus(data.message || '模板任务已启动', 'success')
    return data
  },

  async stopTasks() {
    const runningTasks = state.tasks.value.filter((task) => task?.status === 'running' && task?.task_id)
    if (!runningTasks.length) {
      actions.setStatus('当前没有运行中的任务', 'info')
      return
    }
    await Promise.all(runningTasks.map((task) => actions.stopTask(task.task_id, task.kind || 'script')))
    actions.setStatus(`已停止 ${runningTasks.length} 个任务`, 'success')
  },

  async openTemplateEditor(meta = null, callback = null) {
    state.templateEditorModalVisible.value = true
    state.templateEditorModalData.value = meta
    state.templateEditorModalCallback.value = callback
  },

  async closeTemplateEditor() {
    state.templateEditorModalVisible.value = false
    state.templateEditorModalData.value = null
    state.templateEditorModalCallback.value = null
  },

  async saveTemplateEditorMeta(meta) {
    if (typeof state.templateEditorModalCallback.value === 'function') {
      await state.templateEditorModalCallback.value(meta)
    }
    await actions.closeTemplateEditor()
  },

  closeModal,
  pickerActions,
}
