import { computed, nextTick, ref, watch } from 'vue'
import {
  buildTemplatePayload,
  countTaskReferences,
  countVariableReferences,
  createEmptyTemplate,
  createEnumOption,
  createTemplateFlow,
  createTemplateFlowStep,
  createTemplateTask,
  createTemplateVariable,
  createStepArgBinding,
  normalizeTemplateEditorData,
  normalizeStepArgBinding,
  removeTaskReferences,
  removeVariableReferences,
  renameVariableReferences,
  validateTemplateDraft,
} from '../../features/templates/editor/templateEditorDomain.js'
import { createTemplateAutosave } from './templateAutosave.js'

const EMPTY_PICKER_STATE = {
  show: false,
  title: '',
  summary: '',
  mode: 'multiple',
  search: '',
  options: [],
  value: [],
  onConfirm: null,
}

const EMPTY_STEP_ARG_STATE = {
  show: false,
  flowKey: '',
  stepKey: '',
  taskKey: '',
  selectedKeys: [],
  rows: [],
}

export function useTemplateEditor({
  state,
  message,
  getProcedureDefinitions,
  closeEditor,
  saveEditorMeta,
  autosaveDelay,
  scheduler,
}) {
  const variableSearch = ref('')
  const localData = ref(createEmptyTemplate())
  const varsList = ref([])
  const procedureDefinitions = ref([])
  const pickerState = ref({ ...EMPTY_PICKER_STATE })
  const stepArgEditorState = ref({ ...EMPTY_STEP_ARG_STATE })
  const settingsDialogVisible = ref(false)
  const variableDialogVisible = ref(false)
  const taskDialogVisible = ref(false)
  const selectedFlowIndex = ref(0)
  const selectedStepIndex = ref(0)
  const autosaveStatus = ref('saved')
  const isClosing = ref(false)
  let autosaveReady = false
  let initializationGeneration = 0
  let editRevision = 0
  let savedRevision = 0

  const templateValidationErrors = computed(() => validateTemplateDraft(localData.value, varsList.value, {
    procedureNames: procedureDefinitions.value.map(item => item.name),
  }))
  const autosaveStatusText = computed(() => {
    if (templateValidationErrors.value.length) return '配置有错误，尚未保存'
    return ({
      pending: '等待自动保存',
      saving: '正在自动保存…',
      saved: '已自动保存',
      error: '自动保存失败',
      invalid: '配置有错误，尚未保存',
    })[autosaveStatus.value]
  })

  const autosave = createTemplateAutosave({
    delay: autosaveDelay,
    scheduler,
    save: async ({ revision, payload }) => {
      autosaveStatus.value = 'saving'
      try {
        await saveEditorMeta(payload)
        savedRevision = Math.max(savedRevision, revision)
        autosaveStatus.value = templateValidationErrors.value.length
          ? 'invalid'
          : (savedRevision === editRevision ? 'saved' : 'pending')
      } catch (error) {
        autosaveStatus.value = 'error'
        throw error
      }
    },
  })

  const visible = computed({
    get: () => state.templateEditorModalVisible.value,
    set: value => {
      if (value) state.templateEditorModalVisible.value = true
      else void handleClose()
    },
  })

  const tpOptions = [
    { label: '文本 (str)', value: 'str' },
    { label: '整数 (int)', value: 'int' },
    { label: '数值 (num)', value: 'num' },
    { label: '布尔 (bool)', value: 'bool' },
    { label: '枚举 (enum)', value: 'enum' },
    { label: 'JSON (json)', value: 'json' },
  ]
  const strUiOptions = [
    { label: '普通文本', value: '' },
    { label: '文件路径', value: 'path' },
  ]
  const onFailOptions = [
    { label: '失败即停止', value: 'stop' },
    { label: '失败后继续', value: 'continue' },
    { label: '跳转到指定任务', value: 'goto' },
  ]
  const onSuccessOptions = [
    { label: '继续下一个任务', value: 'continue' },
    { label: '跳转到指定任务', value: 'goto' },
    { label: '退出任务流', value: 'exit' },
  ]
  const flattenedVarOptions = computed(() => varsList.value
    .map(item => item._key ? ({
      value: item._key,
      label: item.t ? `${item.t} (${item._key})` : item._key,
      desc: item.if?.k ? `依赖 ${item.if.k}` : (item.note || '顶层变量'),
      source: item.if?.k ? 'child' : 'top',
    }) : null)
    .filter(Boolean))

  const procedureOptions = computed(() => procedureDefinitions.value
    .filter(item => item.args.length === 1 && item.args[0] === 'args')
    .map(item => ({ label: item.signature, value: item.name })))

  const taskOptions = computed(() => (localData.value.tasks || [])
    .filter(item => item.k)
    .map(item => ({ label: item.t ? `${item.t} (${item.k})` : item.k, value: item.k })))

  const flowOptions = computed(() => (localData.value.flows || []).map((flow, index) => ({
    label: flow.t ? `${flow.t} (${flow.k || `flow_${index + 1}`})` : (flow.k || `任务流 ${index + 1}`),
    value: index,
  })))

  const selectedFlow = computed(() => localData.value.flows?.[selectedFlowIndex.value] || null)
  const selectedStep = computed(() => selectedFlow.value?.steps?.[selectedStepIndex.value] || null)

  const flowVariableOptions = computed(() => {
    const allowedKeys = new Set(selectedFlow.value?.g || [])
    return flattenedVarOptions.value.filter(item => allowedKeys.has(item.value))
  })

  const bindingSourceOptions = computed(() => [
    { label: '任务流参数', value: 'var', disabled: !flowVariableOptions.value.length },
    { label: '固定值', value: 'literal' },
  ])

  const stepArgSourceOptions = computed(() => [
    { label: '直接填写固定值', value: '__literal__' },
    ...flowVariableOptions.value.map(item => ({ label: item.label, value: item.value })),
  ])

  const gotoStepOptions = computed(() => (selectedFlow.value?.steps || [])
    .filter((_, index) => index !== selectedStepIndex.value)
    .map((step, index) => ({
      label: step.k ? `${step.k}${step.task ? ` (${step.task})` : ''}` : `任务 ${index + 1}`,
      value: step.k,
    }))
    .filter(item => item.value))

  const filteredVarsList = computed(() => {
    const keyword = variableSearch.value.trim().toLowerCase()
    if (!keyword) return varsList.value
    return varsList.value.filter(item => [item._key, item.t, item.note, item.tp]
      .filter(Boolean)
      .some(text => String(text).toLowerCase().includes(keyword)))
  })

  const pickerFilteredOptions = computed(() => {
    const keyword = pickerState.value.search.trim().toLowerCase()
    if (!keyword) return pickerState.value.options
    return pickerState.value.options.filter(item => [item.value, item.label, item.desc]
      .filter(Boolean)
      .some(text => String(text).toLowerCase().includes(keyword)))
  })

  const stats = computed(() => ({
    vars: varsList.value.length,
    requiredVars: varsList.value.filter(item => item.req).length,
    tasks: localData.value.tasks?.length || 0,
    flows: localData.value.flows?.length || 0,
    flowSteps: (localData.value.flows || []).reduce((total, flow) => total + (flow.steps?.length || 0), 0),
  }))

  const stepBindingRows = computed(() => {
    const step = selectedStep.value
    const task = getTaskByKey(step?.task)
    if (!step || !task) return []
    return (task.args || [])
      .filter(key => Object.prototype.hasOwnProperty.call(step.args || {}, key))
      .map(key => ({
        ...getVarMeta(key),
        binding: normalizeStepArgBinding(step.args[key]),
      }))
  })

  const stepBindingStats = computed(() => ({
    total: stepBindingRows.value.length,
    complete: stepBindingRows.value.filter(row => (
      row.binding.$bind !== 'var' || flowVariableOptions.value.some(item => item.value === row.binding.key)
    )).length,
  }))

  function refreshProcedureDefinitions() {
    procedureDefinitions.value = getProcedureDefinitions().map(item => {
      const info = item.block?.getProcedureDef?.()
      const args = Array.isArray(info?.[1])
        ? info[1].map(arg => String(arg || '').trim()).filter(Boolean)
        : Array.isArray(item.block?.arguments_)
          ? item.block.arguments_.map(arg => String(arg || '').trim()).filter(Boolean)
          : []
      return {
        name: item.name,
        args,
        hasReturn: item.hasReturn,
        signature: `${item.name}(${args.join(', ')})${item.hasReturn ? ' → return' : ''}`,
      }
    })
  }

  async function initialize(data) {
    const generation = ++initializationGeneration
    autosave.cancelPending()
    autosaveReady = false
    editRevision = 0
    savedRevision = 0
    autosaveStatus.value = 'saved'
    variableSearch.value = ''
    pickerState.value = { ...EMPTY_PICKER_STATE }
    stepArgEditorState.value = { ...EMPTY_STEP_ARG_STATE }
    settingsDialogVisible.value = false
    variableDialogVisible.value = false
    taskDialogVisible.value = false
    selectedFlowIndex.value = 0
    selectedStepIndex.value = 0
    refreshProcedureDefinitions()
    const normalized = normalizeTemplateEditorData(data || {})
    localData.value = normalized.localData
    varsList.value = normalized.varsList
    await nextTick()
    if (generation === initializationGeneration) {
      autosaveReady = true
      autosaveStatus.value = templateValidationErrors.value.length ? 'invalid' : 'saved'
    }
  }

  function getProcedureByName(name) {
    const normalized = String(name || '').trim()
    return normalized ? procedureDefinitions.value.find(item => item.name === normalized) || null : null
  }

  function getTaskByKey(taskKey) {
    return (localData.value.tasks || []).find(item => item.k === taskKey) || null
  }

  function getFlowStep(flowKey, stepKey) {
    const flow = (localData.value.flows || []).find(item => item.k === flowKey)
    return (flow?.steps || []).find(item => item.k === stepKey) || null
  }

  function getVarMeta(varKey) {
    const field = varsList.value.find(item => item._key === varKey)
    if (!field) return { key: varKey, label: varKey, tp: 'str', def: '', note: '', source: 'unknown' }
    return {
      key: varKey,
      label: field.t || varKey,
      tp: field.tp,
      def: field.def,
      note: field.note || '',
      source: field.if?.k ? 'child' : 'top',
    }
  }

  function formatValuePreview(value) {
    if (typeof value === 'string') return value
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    if (value === null || typeof value === 'undefined') return 'null'
    return String(value)
  }

  function normalizeStepArgEditorRow(key, currentValue) {
    const meta = getVarMeta(key)
    const hasCurrent = typeof currentValue !== 'undefined'
    const binding = hasCurrent
      ? normalizeStepArgBinding(currentValue)
      : createStepArgBinding('literal', buildDefaultStepArgValue(key))
    return { key, label: meta.label, tp: meta.tp, binding, meta }
  }

  function enumOptionsForKey(varKey) {
    const field = varsList.value.find(item => item._key === varKey)
    if (!field || field.tp !== 'enum') return []
    return (field.oneOf || []).map(item => ({ label: item.t || item.v || '', value: item.v || '' }))
  }

  function duplicateVar(value) {
    const index = varsList.value.findIndex(item => item === value)
    const clone = JSON.parse(JSON.stringify(value))
    clone._key = clone._key ? `${clone._key}_copy` : ''
    if (index === -1) varsList.value.push(clone)
    else varsList.value.splice(index + 1, 0, clone)
  }

  function syncStepArgEditorReferences(from, to) {
    if (!stepArgEditorState.value.rows.length) return
    const nextRows = []
    const seen = new Set()
    for (const row of stepArgEditorState.value.rows) {
      const key = row.key === from ? to : row.key
      if (!key || seen.has(key)) continue
      seen.add(key)
      nextRows.push({
        ...row,
        key,
        value: row.value === from ? to : row.value,
        meta: row.meta?.key === from ? { ...row.meta, key: to } : row.meta,
      })
    }
    stepArgEditorState.value.rows = nextRows
    stepArgEditorState.value.selectedKeys = [...new Set(
      stepArgEditorState.value.selectedKeys.map(key => key === from ? to : key).filter(Boolean),
    )]
  }

  function handleTaskFunctionChange(task) {
    const procedure = getProcedureByName(task.fn)
    if (!procedure) {
      message.warning('未找到对应 Blockly 函数，请先在工作区中定义函数')
      return
    }
    if (!(procedure.args.length === 1 && procedure.args[0] === 'args')) {
      task.fn = ''
      message.warning('任务只能绑定形如 function xxx(args) 的函数')
    }
  }

  function handleStepTaskChange(step) {
    step.args = {}
  }

  function getVariableReferenceCount(variable) {
    const key = String(variable?._key || variable?._referenceKey || '').trim()
    return countVariableReferences({ varsList: varsList.value, localData: localData.value, key })
  }

  function removeVariableDefinition(variable) {
    const key = String(variable?._key || variable?._referenceKey || '').trim()
    const index = varsList.value.indexOf(variable)
    if (index < 0) return
    varsList.value.splice(index, 1)
    if (!key || varsList.value.some(item => String(item?._key || '').trim() === key)) return
    removeVariableReferences({ varsList: varsList.value, localData: localData.value, key })
    stepArgEditorState.value.selectedKeys = stepArgEditorState.value.selectedKeys.filter(item => item !== key)
    stepArgEditorState.value.rows = stepArgEditorState.value.rows.filter(row => (
      row.key !== key && !(row.binding?.$bind === 'var' && row.binding.key === key)
    ))
  }

  function getTaskReferenceCount(task) {
    const key = String(task?.k || task?._referenceKey || '').trim()
    return countTaskReferences(localData.value, key)
  }

  function removeTaskDefinition(task) {
    const key = String(task?.k || task?._referenceKey || '').trim()
    const tasks = localData.value.tasks || []
    const index = tasks.indexOf(task)
    if (index < 0) return
    tasks.splice(index, 1)
    if (!key || tasks.some(item => String(item?.k || '').trim() === key)) return
    removeTaskReferences(localData.value, key)
    if (stepArgEditorState.value.taskKey === key) closeStepArgEditor()
    selectedStepIndex.value = Math.max(
      0,
      Math.min(selectedStepIndex.value, (selectedFlow.value?.steps?.length || 1) - 1),
    )
  }

  function setVariableKey(variable, value) {
    const previousKey = String(variable._referenceKey || variable._key || '').trim()
    variable._key = value
    const nextKey = String(value || '').trim()
    if (!nextKey) {
      if (previousKey) variable._referenceKey = previousKey
      return
    }
    if (previousKey && previousKey !== nextKey) {
      renameVariableReferences({ varsList: varsList.value, localData: localData.value, from: previousKey, to: nextKey })
      syncStepArgEditorReferences(previousKey, nextKey)
    }
    variable._referenceKey = nextKey
  }

  function setTaskKey(task, value) {
    const previousKey = String(task._referenceKey || task.k || '').trim()
    task.k = value
    const nextKey = String(value || '').trim()
    if (!nextKey) {
      if (previousKey) task._referenceKey = previousKey
      return
    }
    if (previousKey && previousKey !== nextKey) {
      for (const flow of localData.value.flows || []) {
        for (const step of flow.steps || []) {
          if (step.task === previousKey) step.task = nextKey
        }
      }
    }
    task._referenceKey = nextKey
  }

  function handleVariableTypeChange(variable) {
    variable.def = variable.tp === 'bool' ? false : (['int', 'num'].includes(variable.tp) ? null : '')
    if (!['int', 'num'].includes(variable.tp)) {
      variable.min = undefined
      variable.max = undefined
    }
    if (variable.tp !== 'str') variable.ui = ''
    if (variable.tp !== 'enum') variable.oneOf = []
  }

  function nextUniqueKey(items, prefix) {
    const used = new Set((items || []).map(item => item.k).filter(Boolean))
    let index = 1
    while (used.has(`${prefix}_${index}`)) index += 1
    return `${prefix}_${index}`
  }

  function selectFlow(index) {
    selectedFlowIndex.value = Number(index) || 0
    selectedStepIndex.value = 0
  }

  function selectStep(index) {
    selectedStepIndex.value = Math.max(0, Number(index) || 0)
  }

  function addFlow() {
    const flow = createTemplateFlow()
    flow.k = nextUniqueKey(localData.value.flows, 'flow')
    flow.t = '新任务流'
    localData.value.flows.push(flow)
    selectFlow(localData.value.flows.length - 1)
  }

  function removeSelectedFlow() {
    if (!selectedFlow.value) return
    localData.value.flows.splice(selectedFlowIndex.value, 1)
    selectedFlowIndex.value = Math.max(0, Math.min(selectedFlowIndex.value, localData.value.flows.length - 1))
    selectedStepIndex.value = 0
  }

  function addStep() {
    const flow = selectedFlow.value
    if (!flow) return
    const step = createTemplateFlowStep()
    step.k = nextUniqueKey(flow.steps, 'step')
    step.task = localData.value.tasks?.[0]?.k || ''
    flow.steps.push(step)
    selectedStepIndex.value = flow.steps.length - 1
  }

  function removeSelectedStep() {
    const flow = selectedFlow.value
    if (!flow || !selectedStep.value) return
    const removedKey = selectedStep.value.k
    flow.steps.splice(selectedStepIndex.value, 1)
    for (const step of flow.steps) {
      if (step.onFail === 'goto' && step.goto === removedKey) {
        step.onFail = 'stop'
        step.goto = ''
      }
      if (step.onSuccess === 'goto' && step.successGoto === removedKey) {
        step.onSuccess = 'continue'
        step.successGoto = ''
      }
    }
    selectedStepIndex.value = Math.max(0, Math.min(selectedStepIndex.value, flow.steps.length - 1))
  }

  function moveSelectedStep(offset) {
    const flow = selectedFlow.value
    const from = selectedStepIndex.value
    const to = from + offset
    if (!flow || to < 0 || to >= flow.steps.length) return
    const [step] = flow.steps.splice(from, 1)
    flow.steps.splice(to, 0, step)
    selectedStepIndex.value = to
  }

  function isStepBindingComplete(step) {
    const task = getTaskByKey(step?.task)
    if (!task) return false
    const allowedKeys = new Set(task.args || [])
    return Object.entries(step.args || {}).every(([key, value]) => {
      if (!allowedKeys.has(key)) return false
      const binding = normalizeStepArgBinding(value)
      return binding.$bind !== 'var' || flowVariableOptions.value.some(item => item.value === binding.key)
    })
  }

  function handleWorkbenchStepTaskChange(taskKey) {
    const step = selectedStep.value
    if (!step) return
    step.task = taskKey || ''
    const task = getTaskByKey(step.task)
    const allowedKeys = new Set(task?.args || [])
    step.args = Object.fromEntries(Object.entries(step.args || {}).filter(([key]) => allowedKeys.has(key)))
  }

  function setStepArgSource(argKey, source) {
    const step = selectedStep.value
    if (!step) return
    const current = Object.prototype.hasOwnProperty.call(step.args || {}, argKey)
      ? normalizeStepArgBinding(step.args[argKey])
      : null
    if (source === 'var') {
      const sameName = flowVariableOptions.value.find(item => item.value === argKey) || flowVariableOptions.value[0]
      const currentKey = current?.$bind === 'var'
        && flowVariableOptions.value.some(item => item.value === current.key)
        ? current.key
        : sameName?.value
      step.args[argKey] = createStepArgBinding('var', currentKey)
    } else {
      const value = current?.$bind === 'literal' ? current.value : buildDefaultStepArgValue(argKey)
      step.args[argKey] = createStepArgBinding('literal', value)
    }
  }

  function setStepArgValue(argKey, value) {
    const step = selectedStep.value
    if (!step) return
    const binding = normalizeStepArgBinding(step.args?.[argKey])
    step.args[argKey] = binding.$bind === 'var'
      ? createStepArgBinding('var', value)
      : createStepArgBinding('literal', value)
  }

  function setSelectedStepKey(value) {
    const flow = selectedFlow.value
    const step = selectedStep.value
    if (!flow || !step) return
    const previousKey = step.k
    step.k = value
    if (!previousKey || previousKey === value) return
    for (const candidate of flow.steps) {
      if (candidate !== step && candidate.onFail === 'goto' && candidate.goto === previousKey) candidate.goto = value
      if (candidate !== step && candidate.onSuccess === 'goto' && candidate.successGoto === previousKey) candidate.successGoto = value
    }
  }

  function handleStepOnSuccessChange(value) {
    const step = selectedStep.value
    if (!step) return
    step.onSuccess = value
    if (value !== 'goto') step.successGoto = ''
  }

  function handleStepOnFailChange(value) {
    const step = selectedStep.value
    if (!step) return
    step.onFail = value
    if (value !== 'goto') step.goto = ''
  }

  function openSettingsDialog() {
    settingsDialogVisible.value = true
  }

  function openVariableDialog() {
    variableDialogVisible.value = true
  }

  function openTaskDialog() {
    refreshProcedureDefinitions()
    taskDialogVisible.value = true
  }

  function closeSettingsDialog() {
    settingsDialogVisible.value = false
  }

  function closeVariableDialog() {
    variableDialogVisible.value = false
  }

  function closeTaskDialog() {
    taskDialogVisible.value = false
  }

  function closePicker() {
    pickerState.value = { ...EMPTY_PICKER_STATE }
  }

  function openPicker({ title, summary = '', options = [], value = [], onConfirm }) {
    pickerState.value = {
      show: true,
      title,
      summary,
      mode: 'multiple',
      search: '',
      options,
      value: Array.isArray(value) ? [...value] : [],
      onConfirm,
    }
  }

  function confirmPicker() {
    pickerState.value.onConfirm?.([...(pickerState.value.value || [])])
    closePicker()
  }

  function closeStepArgEditor() {
    stepArgEditorState.value = { ...EMPTY_STEP_ARG_STATE }
  }

  function buildDefaultStepArgValue(varKey) {
    const meta = getVarMeta(varKey)
    if (meta.tp === 'bool') return true
    if (meta.tp === 'int' || meta.tp === 'num') return meta.def ?? 0
    if (meta.tp === 'enum') return meta.def ?? ''
    return meta.def ?? varKey
  }

  function openTaskVarPicker(task) {
    openPicker({
      title: '选择任务变量',
      summary: '这些变量会被打包进任务函数的 args 对象。',
      options: flattenedVarOptions.value,
      value: task.args || [],
      onConfirm: selected => { task.args = selected },
    })
  }

  function openFlowGlobalPicker(flow) {
    openPicker({
      title: '选择任务流全局参数',
      summary: '这些变量会作为任务流的全局引用参数。',
      options: flattenedVarOptions.value,
      value: flow.g || [],
      onConfirm: selected => { flow.g = selected },
    })
  }

  function openStepArgsPicker(flow, step) {
    const task = getTaskByKey(step.task)
    if (!task) {
      message.warning('请先为该步骤选择任务')
      return
    }
    const rows = (task.args || []).map(key => normalizeStepArgEditorRow(key, step.args?.[key]))
    stepArgEditorState.value = {
      show: true,
      flowKey: flow.k || '',
      stepKey: step.k || '',
      taskKey: step.task || '',
      selectedKeys: rows.filter(row => Object.prototype.hasOwnProperty.call(step.args || {}, row.key)).map(row => row.key),
      rows,
    }
  }

  function confirmStepArgEditor() {
    const step = getFlowStep(stepArgEditorState.value.flowKey, stepArgEditorState.value.stepKey)
    if (!step) return closeStepArgEditor()
    step.args = Object.fromEntries(stepArgEditorState.value.rows
      .filter(row => stepArgEditorState.value.selectedKeys.includes(row.key))
      .map(row => [row.key, row.binding]))
    closeStepArgEditor()
  }

  function setStepArgEditorSource(row, source) {
    const current = normalizeStepArgBinding(row.binding)
    if (source === 'var') {
      const sameName = flowVariableOptions.value.find(item => item.value === row.key) || flowVariableOptions.value[0]
      const currentKey = current.$bind === 'var'
        && flowVariableOptions.value.some(item => item.value === current.key)
        ? current.key
        : sameName?.value
      row.binding = createStepArgBinding('var', currentKey)
      return
    }
    row.binding = createStepArgBinding(
      'literal',
      current.$bind === 'literal' ? current.value : buildDefaultStepArgValue(row.key),
    )
  }

  function handleAddDependentVar(parentVar, eqValue = undefined) {
    if (!parentVar._key) {
      message.warning('请先填写父级参数的键名')
      return
    }
    const child = createTemplateVariable(parentVar._key, eqValue)
    const index = varsList.value.indexOf(parentVar)
    if (index === -1) varsList.value.push(child)
    else varsList.value.splice(index + 1, 0, child)
  }

  async function handleClose() {
    if (isClosing.value) return
    if (templateValidationErrors.value.length) {
      autosaveStatus.value = 'invalid'
      message.warning(templateValidationErrors.value[0])
      return
    }
    isClosing.value = true
    try {
      const snapshot = savedRevision < editRevision
        ? {
            revision: editRevision,
            payload: buildTemplatePayload(localData.value, varsList.value, { clone: true }),
          }
        : undefined
      await autosave.flush(snapshot)
      closeEditor()
    } catch (error) {
      message.warning(error?.message || '自动保存失败，请稍后重试')
    } finally {
      isClosing.value = false
    }
  }

  watch(() => state.templateEditorModalData.value, initialize, { immediate: true })
  watch(
    () => [localData.value, varsList.value],
    () => {
      if (!autosaveReady) return
      editRevision += 1
      if (templateValidationErrors.value.length) {
        autosave.cancelPending()
        autosaveStatus.value = 'invalid'
        return
      }
      autosaveStatus.value = 'pending'
      const payload = buildTemplatePayload(localData.value, varsList.value, { clone: true })
      autosave.schedule({ revision: editRevision, payload })
    },
    { deep: true, flush: 'post' },
  )
  return {
    selectedFlowIndex,
    selectedStepIndex,
    variableSearch,
    autosaveStatus,
    autosaveStatusText,
    templateValidationErrors,
    isClosing,
    visible,
    pickerState,
    stepArgEditorState,
    settingsDialogVisible,
    variableDialogVisible,
    taskDialogVisible,
    localData,
    varsList,
    tpOptions,
    strUiOptions,
    onFailOptions,
    onSuccessOptions,
    bindingSourceOptions,
    stepArgSourceOptions,
    procedureOptions,
    taskOptions,
    flowOptions,
    selectedFlow,
    selectedStep,
    gotoStepOptions,
    stepBindingRows,
    stepBindingStats,
    filteredVarsList,
    pickerFilteredOptions,
    stats,
    refreshProcedureDefinitions,
    createVar: createTemplateVariable,
    createTask: createTemplateTask,
    createFlow: createTemplateFlow,
    createFlowStep: createTemplateFlowStep,
    createEnumOption,
    duplicateVar,
    getVariableReferenceCount,
    removeVariableDefinition,
    getTaskReferenceCount,
    removeTaskDefinition,
    setVariableKey,
    setTaskKey,
    handleVariableTypeChange,
    handleTaskFunctionChange,
    handleStepTaskChange,
    selectFlow,
    selectStep,
    addFlow,
    removeSelectedFlow,
    addStep,
    removeSelectedStep,
    moveSelectedStep,
    isStepBindingComplete,
    handleWorkbenchStepTaskChange,
    setStepArgSource,
    setStepArgValue,
    setSelectedStepKey,
    handleStepOnSuccessChange,
    handleStepOnFailChange,
    openSettingsDialog,
    openVariableDialog,
    openTaskDialog,
    closeSettingsDialog,
    closeVariableDialog,
    closeTaskDialog,
    formatValuePreview,
    enumOptionsForKey,
    closePicker,
    confirmPicker,
    closeStepArgEditor,
    openTaskVarPicker,
    openFlowGlobalPicker,
    openStepArgsPicker,
    confirmStepArgEditor,
    setStepArgEditorSource,
    handleAddDependentVar,
    handleClose,
  }
}
