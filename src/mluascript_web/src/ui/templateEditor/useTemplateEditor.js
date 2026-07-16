import { computed, ref, watch } from 'vue'
import {
  buildTemplatePayload,
  createEmptyTemplate,
  createEnumOption,
  createTemplateFlow,
  createTemplateFlowStep,
  createTemplateTask,
  createTemplateVariable,
  normalizeTemplateEditorData,
  renameVariableReferences,
} from '../../features/templates/editor/templateEditorDomain'

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

export function useTemplateEditor({ state, message, getProcedureDefinitions, closeEditor, saveEditorMeta }) {
  const activeTab = ref('basic')
  const variableSearch = ref('')
  const localData = ref(createEmptyTemplate())
  const varsList = ref([])
  const procedureDefinitions = ref([])
  const pickerState = ref({ ...EMPTY_PICKER_STATE })
  const stepArgEditorState = ref({ ...EMPTY_STEP_ARG_STATE })

  const visible = computed({
    get: () => state.templateEditorModalVisible.value,
    set: value => {
      if (value) state.templateEditorModalVisible.value = true
      else closeEditor()
    },
  })

  const tpOptions = [
    { label: '文本 (str)', value: 'str' },
    { label: '整数 (int)', value: 'int' },
    { label: '布尔 (bool)', value: 'bool' },
    { label: '枚举 (enum)', value: 'enum' },
    { label: '文件路径 (path)', value: 'path' },
  ]
  const onFailOptions = [
    { label: '失败即停止', value: 'stop' },
    { label: '失败后继续', value: 'continue' },
  ]

  const flattenedVarOptions = computed(() => varsList.value
    .map(item => item._key ? ({
      value: item._key,
      label: item.t ? `${item.t} (${item._key})` : item._key,
      desc: item.if?.k ? `依赖 ${item.if.k}` : (item.note || '顶层变量'),
      source: item.if?.k ? 'child' : 'top',
    }) : null)
    .filter(Boolean))

  const stepArgSourceOptions = computed(() => [
    { label: '直接填写默认值', value: '__literal__' },
    ...flattenedVarOptions.value.map(item => ({ label: item.label, value: item.value })),
  ])

  const procedureOptions = computed(() => procedureDefinitions.value
    .filter(item => item.args.length === 1 && item.args[0] === 'args')
    .map(item => ({ label: item.signature, value: item.name })))

  const taskOptions = computed(() => (localData.value.tasks || [])
    .filter(item => item.k)
    .map(item => ({ label: item.t ? `${item.t} (${item.k})` : item.k, value: item.k })))

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

  const templatePreview = computed(() => JSON.stringify(
    buildTemplatePayload(localData.value, varsList.value, { clone: true }),
    null,
    2,
  ))

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

  function initialize(data) {
    activeTab.value = 'basic'
    variableSearch.value = ''
    pickerState.value = { ...EMPTY_PICKER_STATE }
    stepArgEditorState.value = { ...EMPTY_STEP_ARG_STATE }
    refreshProcedureDefinitions()
    const normalized = normalizeTemplateEditorData(data || {})
    localData.value = normalized.localData
    varsList.value = normalized.varsList
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
    let editorType = 'text'
    let value = hasCurrent ? currentValue : (meta.def ?? '')
    let sourceMode = 'literal'
    if (typeof currentValue === 'string') {
      const matchesVariable = flattenedVarOptions.value.some(item => item.value === currentValue)
      sourceMode = matchesVariable && currentValue !== key ? 'var' : 'literal'
    }
    if (meta.tp === 'bool') {
      editorType = 'bool'
      value = hasCurrent ? Boolean(currentValue) : Boolean(meta.def ?? false)
    } else if (meta.tp === 'int') {
      editorType = 'number'
      value = hasCurrent ? Number(currentValue) : (meta.def ?? 0)
    } else if (meta.tp === 'enum') {
      editorType = 'enum'
    }
    return { key, label: meta.label, tp: meta.tp, editorType, sourceMode, value, meta }
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
    if (meta.tp === 'int') return meta.def ?? 0
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
      .map(row => [row.key, row.value]))
    closeStepArgEditor()
  }

  function fillArgsFromTask(step) {
    const task = getTaskByKey(step.task)
    if (!task) {
      message.warning('未找到对应任务，无法自动生成步骤默认值')
      return
    }
    step.args = Object.fromEntries((task.args || [])
      .filter(Boolean)
      .map(arg => [arg, buildDefaultStepArgValue(arg)]))
    message.success('已根据变量类型自动生成步骤默认值')
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

  function warnOnTab(tab, text) {
    activeTab.value = tab
    message.warning(text)
    return false
  }

  function validateTemplate() {
    if (!localData.value.id) return warnOnTab('basic', '模板 ID 不能为空')
    const variableKeys = varsList.value.map(item => item._key).filter(Boolean)
    const duplicateVariable = variableKeys.find((key, index) => variableKeys.indexOf(key) !== index)
    if (duplicateVariable) return warnOnTab('vars', `存在重复参数键名: ${duplicateVariable}`)

    const invalidTask = (localData.value.tasks || []).find(item => !item.k || !item.fn)
    if (invalidTask) return warnOnTab('tasks', '任务必须填写任务 Key 和 Lua 函数名')
    const taskKeys = (localData.value.tasks || []).map(item => item.k).filter(Boolean)
    const duplicateTask = taskKeys.find((key, index) => taskKeys.indexOf(key) !== index)
    if (duplicateTask) return warnOnTab('tasks', `存在重复任务 Key: ${duplicateTask}`)

    const variableKeySet = new Set(flattenedVarOptions.value.map(item => item.value))
    for (const task of localData.value.tasks || []) {
      const procedure = getProcedureByName(task.fn)
      if (!procedure) return warnOnTab('tasks', `任务引用了不存在的 Blockly 函数: ${task.fn}`)
      if (!(procedure.args.length === 1 && procedure.args[0] === 'args')) {
        return warnOnTab('tasks', `任务只能绑定形如 function xxx(args) 的函数: ${task.fn}`)
      }
      const missingArg = (task.args || []).find(arg => !variableKeySet.has(arg))
      if (missingArg) return warnOnTab('tasks', `任务变量不存在: ${missingArg}`)
    }

    const taskKeySet = new Set(taskKeys)
    for (const flow of localData.value.flows || []) {
      if (!flow.k) return warnOnTab('flows', '任务流必须填写 Key')
      const missingGlobal = (flow.g || []).find(arg => !variableKeySet.has(arg))
      if (missingGlobal) return warnOnTab('flows', `任务流全局参数不存在: ${missingGlobal}`)
      const stepKeys = new Set()
      for (const step of flow.steps || []) {
        if (!step.k || !step.task) return warnOnTab('flows', '任务流步骤必须填写步骤 ID 和任务')
        if (stepKeys.has(step.k)) return warnOnTab('flows', `任务流内存在重复步骤 ID: ${step.k}`)
        stepKeys.add(step.k)
        if (!taskKeySet.has(step.task)) return warnOnTab('flows', `任务流步骤引用了不存在的任务: ${step.task}`)
      }
    }
    return true
  }

  async function handleSave() {
    if (!validateTemplate()) return
    await saveEditorMeta(buildTemplatePayload(localData.value, varsList.value))
    message.success('已保存模板配置到拼图块')
  }

  function handleClose() {
    closeEditor()
  }

  watch(() => state.templateEditorModalData.value, initialize, { immediate: true })
  watch(
    () => varsList.value.map(item => item._key),
    (nextKeys, previousKeys) => {
      if (!Array.isArray(previousKeys) || previousKeys.length !== nextKeys.length) return
      for (let index = 0; index < nextKeys.length; index += 1) {
        const from = String(previousKeys[index] || '').trim()
        const to = String(nextKeys[index] || '').trim()
        if (!from || !to || from === to) continue
        renameVariableReferences({ varsList: varsList.value, localData: localData.value, from, to })
        syncStepArgEditorReferences(from, to)
      }
    },
    { flush: 'sync' },
  )

  return {
    activeTab,
    variableSearch,
    visible,
    pickerState,
    stepArgEditorState,
    localData,
    varsList,
    tpOptions,
    onFailOptions,
    stepArgSourceOptions,
    procedureOptions,
    taskOptions,
    filteredVarsList,
    pickerFilteredOptions,
    stats,
    templatePreview,
    createVar: createTemplateVariable,
    createTask: createTemplateTask,
    createFlow: createTemplateFlow,
    createFlowStep: createTemplateFlowStep,
    createEnumOption,
    duplicateVar,
    handleTaskFunctionChange,
    handleStepTaskChange,
    formatValuePreview,
    enumOptionsForKey,
    closePicker,
    confirmPicker,
    closeStepArgEditor,
    openTaskVarPicker,
    openFlowGlobalPicker,
    openStepArgsPicker,
    confirmStepArgEditor,
    fillArgsFromTask,
    handleAddDependentVar,
    handleSave,
    handleClose,
  }
}
