<script setup>
import { computed, ref, watch } from 'vue'
import {
  NModal,
  NTabs,
  NTabPane,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NDynamicInput,
  NButton,
  NSpace,
  NCollapse,
  NCollapseItem,
  NTag,
  NText,
  NDivider,
  NAlert,
  NScrollbar,
  NCheckbox,
  useMessage
} from 'naive-ui'
import { getWorkspaceProcedureDefinitions } from '../blockly/utils'
import { state } from '../store'

const message = useMessage()
const activeTab = ref('basic')
const variableSearch = ref('')
const visible = computed({
  get: () => state.templateEditorModalVisible.value,
  set: (val) => { state.templateEditorModalVisible.value = val }
})

const pickerState = ref({
  show: false,
  title: '',
  summary: '',
  mode: 'multiple',
  search: '',
  options: [],
  value: [],
  onConfirm: null,
})

const stepArgEditorState = ref({
  show: false,
  flowKey: '',
  stepKey: '',
  taskKey: '',
  selectedKeys: [],
  rows: [],
})

function createEmptyTemplate() {
  return {
    v: 1,
    id: '',
    t: '',
    d: '',
    vars: {},
    tasks: [],
    flows: []
  }
}

function createVar(parentKey = '', eqValue = undefined) {
  return {
    _key: '',
    t: '',
    tp: 'str',
    def: '',
    req: false,
    note: '',
    min: undefined,
    max: undefined,
    oneOf: [],
    if: parentKey ? { k: parentKey, eq: eqValue !== undefined ? String(eqValue) : '' } : null,
    _showAdvanced: parentKey ? true : false
  }
}

function createTask() {
  return {
    k: '',
    t: '',
    fn: '',
    args: [],
    _fnArgs: ['args']
  }
}

function createFlow() {
  return {
    k: '',
    t: '',
    g: [],
    steps: []
  }
}

function createFlowStep() {
  return {
    k: '',
    task: '',
    args: {},
    onFail: 'stop'
  }
}

const localData = ref(createEmptyTemplate())
const varsList = ref([])
const procedureDefinitions = ref([])

const tpOptions = [
  { label: '文本 (str)', value: 'str' },
  { label: '整数 (int)', value: 'int' },
  { label: '布尔 (bool)', value: 'bool' },
  { label: '枚举 (enum)', value: 'enum' },
  { label: '文件路径 (path)', value: 'path' }
]

const onFailOptions = [
  { label: '失败即停止', value: 'stop' },
  { label: '失败后继续', value: 'continue' }
]

const stepArgSourceOptions = computed(() => [
  { label: '直接填写默认值', value: '__literal__' },
  ...flattenedVarOptions.value.map((item) => ({
    label: item.label,
    value: item.value,
  }))
])

const procedureOptions = computed(() => procedureDefinitions.value
  .filter((item) => item.args.length === 1 && item.args[0] === 'args')
  .map((item) => ({
    label: item.signature,
    value: item.name
  })))

const taskOptions = computed(() => (localData.value.tasks || [])
  .filter((item) => item.k)
  .map((item) => ({
    label: item.t ? `${item.t} (${item.k})` : item.k,
    value: item.k,
  })))

const filteredVarsList = computed(() => {
  const keyword = variableSearch.value.trim().toLowerCase()
  if (!keyword) return varsList.value
  return varsList.value.filter(item => {
    return [item._key, item.t, item.note, item.tp]
      .filter(Boolean)
      .some(text => String(text).toLowerCase().includes(keyword))
  })
})

const flattenedVarOptions = computed(() => buildFlattenedVarOptions())

const pickerFilteredOptions = computed(() => {
  const keyword = pickerState.value.search.trim().toLowerCase()
  if (!keyword) return pickerState.value.options
  return pickerState.value.options.filter(item => {
    return [item.value, item.label, item.desc]
      .filter(Boolean)
      .some(text => String(text).toLowerCase().includes(keyword))
  })
})

const stats = computed(() => ({
  vars: varsList.value.length,
  requiredVars: varsList.value.filter(item => item.req).length,
  tasks: Array.isArray(localData.value.tasks) ? localData.value.tasks.length : 0,
  flows: Array.isArray(localData.value.flows) ? localData.value.flows.length : 0,
  flowSteps: (localData.value.flows || []).reduce((total, flow) => total + (flow.steps?.length || 0), 0)
}))

const templatePreview = computed(() => {
  const result = buildTemplatePayload({ trimForPreview: true })
  return JSON.stringify(result, null, 2)
})

watch(visible, (val) => {
  if (!val) return
  const data = state.templateEditorModalData.value || {}
  activeTab.value = 'basic'
  variableSearch.value = ''
  closePicker()
  closeStepArgEditor()
  refreshProcedureDefinitions()
  localData.value = {
    v: data.v || 1,
    id: data.id || '',
    t: data.t || '',
    d: data.d || '',
    tasks: Array.isArray(data.tasks) ? data.tasks.map(task => normalizeTask(task)) : [],
    flows: Array.isArray(data.flows) ? data.flows.map(flow => ({
      k: flow.k || '',
      t: flow.t || '',
      g: Array.isArray(flow.g) ? [...flow.g] : [],
      steps: Array.isArray(flow.steps) ? flow.steps.map(step => ({
        k: step.k || '',
        task: step.task || '',
        args: step.args && typeof step.args === 'object' ? { ...step.args } : {},
        onFail: step.onFail || 'stop'
      })) : []
    })) : []
  }
  const varsObj = data.vars || {}
  varsList.value = flattenParsedVars(varsObj)
})

function flattenParsedVars(varsObj) {
  const result = []
  
  function traverse(key, value, implicitIf) {
    const normalized = normalizeVar(key, value)
    
    if (!normalized.if && implicitIf) {
      normalized.if = { k: implicitIf.k, eq: implicitIf.eq !== undefined ? String(implicitIf.eq) : '' }
    }
    if (normalized.if) {
      normalized._showAdvanced = true
    }
    
    result.push(normalized)
    
    if (Array.isArray(value.children)) {
      for (const child of value.children) {
        const eqVal = value.tp === 'bool' ? 'true' : ''
        traverse(child.k || '', child, { k: key, eq: eqVal })
      }
    }
    
    if (Array.isArray(value.oneOf)) {
      for (const option of value.oneOf) {
        if (Array.isArray(option.children)) {
          for (const child of option.children) {
            traverse(child.k || '', child, { k: key, eq: option.v })
          }
        }
      }
    }
  }
  
  for (const [key, value] of Object.entries(varsObj || {})) {
    traverse(key, value, null)
  }
  
  return result
}

function refreshProcedureDefinitions() {
  const definitions = getWorkspaceProcedureDefinitions()
  procedureDefinitions.value = definitions.map((item) => {
    const info = item.block?.getProcedureDef?.()
    const args = Array.isArray(info?.[1])
      ? info[1].map((arg) => String(arg || '').trim()).filter(Boolean)
      : Array.isArray(item.block?.arguments_)
        ? item.block.arguments_.map((arg) => String(arg || '').trim()).filter(Boolean)
        : []
    return {
      name: item.name,
      args,
      hasReturn: item.hasReturn,
      signature: `${item.name}(${args.join(', ')})${item.hasReturn ? ' → return' : ''}`
    }
  })
}

function normalizeTask(task = {}) {
  return {
    k: task.k || '',
    t: task.t || '',
    fn: task.fn || '',
    args: Array.isArray(task.args) ? task.args.filter(Boolean) : [],
    _fnArgs: ['args']
  }
}

function normalizeVar(key, value = {}) {
  return {
    _key: key !== undefined ? key : (value.k || ''),
    t: value.t || '',
    tp: value.tp || 'str',
    def: value.def !== undefined ? value.def : defaultValueForType(value.tp || 'str'),
    req: Boolean(value.req),
    note: value.note || '',
    min: value.min,
    max: value.max,
    oneOf: Array.isArray(value.oneOf) ? value.oneOf.map(item => normalizeEnumOption(item)) : [],
    if: value.if && value.if.k ? { k: value.if.k, eq: normalizeIfValue(value.if.eq) } : null,
    _showAdvanced: false
  }
}

function normalizeEnumOption(option) {
  if (option && typeof option === 'object') {
    return {
      v: option.v ?? '',
      t: option.t ?? ''
    }
  }
  return { v: option ?? '', t: '' }
}

function normalizeIfValue(rawValue) {
  if (rawValue === undefined || rawValue === null || rawValue === '') return ''
  if (typeof rawValue === 'boolean') return rawValue ? 'true' : 'false'
  return String(rawValue)
}

function defaultValueForType(tp) {
  if (tp === 'bool') return false
  if (tp === 'int') return null
  return ''
}

function createEnumOption() {
  return { v: '', t: '', children: [] }
}

function getProcedureByName(name) {
  const normalized = String(name || '').trim()
  if (!normalized) return null
  return procedureDefinitions.value.find(item => item.name === normalized) || null
}

function getTaskByKey(taskKey) {
  return (localData.value.tasks || []).find(item => item.k === taskKey) || null
}

function getFlowByKey(flowKey) {
  return (localData.value.flows || []).find(item => item.k === flowKey) || null
}

function getFlowStep(flowKey, stepKey) {
  const flow = getFlowByKey(flowKey)
  if (!flow) return null
  return (flow.steps || []).find(item => item.k === stepKey) || null
}


function getVarMeta(varKey) {
  const topField = varsList.value.find(item => item._key === varKey)
  if (topField) {
    return {
      key: varKey,
      label: topField.t || varKey,
      tp: topField.tp,
      def: topField.def,
      note: topField.note || '',
      source: topField.if?.k ? 'child' : 'top',
    }
  }
  return {
    key: varKey,
    label: varKey,
    tp: 'str',
    def: '',
    note: '',
    source: 'unknown',
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
    const matchesVar = flattenedVarOptions.value.some(item => item.value === currentValue)
    sourceMode = matchesVar && currentValue !== key ? 'var' : 'literal'
  }

  if (meta.tp === 'bool') {
    editorType = 'bool'
    value = hasCurrent ? Boolean(currentValue) : Boolean(meta.def ?? false)
  } else if (meta.tp === 'int') {
    editorType = 'number'
    value = hasCurrent ? Number(currentValue) : (meta.def ?? 0)
  } else if (meta.tp === 'enum') {
    editorType = 'enum'
    value = hasCurrent ? currentValue : (meta.def ?? '')
  } else {
    editorType = 'text'
    value = hasCurrent ? currentValue : (meta.def ?? '')
  }

  return {
    key,
    label: meta.label,
    tp: meta.tp,
    editorType,
    sourceMode,
    value,
    meta,
  }
}

function enumOptionsForKey(varKey) {
  const topField = varsList.value.find(item => item._key === varKey)
  if (!topField || topField.tp !== 'enum') return []
  return (topField.oneOf || []).map(item => ({
    label: item.t || item.v || '',
    value: item.v || '',
  }))
}

function duplicateVar(value) {
  const index = varsList.value.findIndex(item => item === value)
  const clone = JSON.parse(JSON.stringify(value))
  clone._key = clone._key ? `${clone._key}_copy` : ''
  if (index !== -1) {
    varsList.value.splice(index + 1, 0, clone)
  } else {
    varsList.value.push(clone)
  }
}

function syncVarReferences(oldKey, newKey) {
  const from = String(oldKey || '').trim()
  const to = String(newKey || '').trim()
  if (!from || from === to) return

  for (const item of varsList.value) {
    if (item?.if?.k === from) {
      item.if.k = to
    }
  }

  for (const task of localData.value.tasks || []) {
    if (!Array.isArray(task.args)) continue
    const nextArgs = []
    const seenArgs = new Set()
    for (const arg of task.args) {
      const mappedArg = arg === from ? to : arg
      const normalizedArg = String(mappedArg || '').trim()
      if (!normalizedArg || seenArgs.has(normalizedArg)) continue
      seenArgs.add(normalizedArg)
      nextArgs.push(normalizedArg)
    }
    task.args = nextArgs
  }

  for (const flow of localData.value.flows || []) {
    if (Array.isArray(flow.g)) {
      const nextGlobals = []
      const seenGlobals = new Set()
      for (const arg of flow.g) {
        const mappedArg = arg === from ? to : arg
        const normalizedArg = String(mappedArg || '').trim()
        if (!normalizedArg || seenGlobals.has(normalizedArg)) continue
        seenGlobals.add(normalizedArg)
        nextGlobals.push(normalizedArg)
      }
      flow.g = nextGlobals
    }
    for (const step of flow.steps || []) {
      if (!step?.args || typeof step.args !== 'object') continue
      const nextArgs = {}
      for (const [argKey, argValue] of Object.entries(step.args)) {
        const mappedKey = argKey === from ? to : argKey
        if (!mappedKey || Object.prototype.hasOwnProperty.call(nextArgs, mappedKey)) continue
        nextArgs[mappedKey] = argValue === from ? to : argValue
      }
      step.args = nextArgs
    }
  }

  if (stepArgEditorState.value?.rows?.length) {
    const nextRows = []
    const seenRowKeys = new Set()
    for (const row of stepArgEditorState.value.rows) {
      const nextKey = row.key === from ? to : row.key
      if (!nextKey || seenRowKeys.has(nextKey)) continue
      seenRowKeys.add(nextKey)
      nextRows.push({
        ...row,
        key: nextKey,
        value: row.value === from ? to : row.value,
        meta: row.meta?.key === from ? { ...row.meta, key: to } : row.meta,
      })
    }
    stepArgEditorState.value.rows = nextRows
    stepArgEditorState.value.selectedKeys = [...new Set(stepArgEditorState.value.selectedKeys.map((key) => (key === from ? to : key)).filter(Boolean))]
  }
}

watch(
  () => varsList.value.map((item) => item._key),
  (nextKeys, prevKeys) => {
    if (!Array.isArray(prevKeys) || prevKeys.length !== nextKeys.length) return
    for (let index = 0; index < nextKeys.length; index += 1) {
      const prevKey = String(prevKeys[index] || '').trim()
      const nextKey = String(nextKeys[index] || '').trim()
      if (!prevKey || !nextKey || prevKey === nextKey) continue
      syncVarReferences(prevKey, nextKey)
    }
  },
  { flush: 'sync' }
)

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

function buildFlattenedVarOptions() {
  return varsList.value.map(item => {
    if (!item._key) return null
    return {
      value: item._key,
      label: item.t ? `${item.t} (${item._key})` : item._key,
      desc: item.if?.k ? `依赖 ${item.if.k}` : (item.note || '顶层变量'),
      source: item.if?.k ? 'child' : 'top'
    }
  }).filter(Boolean)
}

function closePicker() {
  pickerState.value = {
    show: false,
    title: '',
    summary: '',
    mode: 'multiple',
    search: '',
    options: [],
    value: [],
    onConfirm: null,
  }
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
  if (typeof pickerState.value.onConfirm === 'function') {
    pickerState.value.onConfirm([...(pickerState.value.value || [])])
  }
  closePicker()
}

function closeStepArgEditor() {
  stepArgEditorState.value = {
    show: false,
    flowKey: '',
    stepKey: '',
    taskKey: '',
    selectedKeys: [],
    rows: [],
  }
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
    onConfirm: (selected) => {
      task.args = selected
    }
  })
}

function openFlowGlobalPicker(flow) {
  openPicker({
    title: '选择任务流全局参数',
    summary: '这些变量会作为任务流的全局引用参数。',
    options: flattenedVarOptions.value,
    value: flow.g || [],
    onConfirm: (selected) => {
      flow.g = selected
    }
  })
}

function openStepArgsPicker(flow, step) {
  const task = getTaskByKey(step.task)
  if (!task) {
    message.warning('请先为该步骤选择任务')
    return
  }
  const rows = (task.args || []).map((key) => normalizeStepArgEditorRow(key, step.args?.[key]))
  const selectedKeys = rows
    .filter(row => Object.prototype.hasOwnProperty.call(step.args || {}, row.key))
    .map(row => row.key)
  stepArgEditorState.value = {
    show: true,
    flowKey: flow.k || '',
    stepKey: step.k || '',
    taskKey: step.task || '',
    selectedKeys,
    rows,
  }
}

function confirmStepArgEditor() {
  const step = getFlowStep(stepArgEditorState.value.flowKey, stepArgEditorState.value.stepKey)
  if (!step) {
    closeStepArgEditor()
    return
  }
  const nextArgs = {}
  for (const row of stepArgEditorState.value.rows) {
    if (!stepArgEditorState.value.selectedKeys.includes(row.key)) continue
    nextArgs[row.key] = row.value
  }
  step.args = nextArgs
  closeStepArgEditor()
}

function fillArgsFromTask(step) {
  const task = getTaskByKey(step.task)
  if (!task) {
    message.warning('未找到对应任务，无法自动生成步骤默认值')
    return
  }
  const nextArgs = {}
  for (const arg of task.args || []) {
    if (arg) nextArgs[arg] = buildDefaultStepArgValue(arg)
  }
  step.args = nextArgs
  message.success('已根据变量类型自动生成步骤默认值')
}

function cleanEnumOptions(list) {
  return (list || [])
    .map(item => {
      return {
        v: item?.v ?? '',
        t: item?.t ?? ''
      }
    })
    .filter(item => item.v !== '')
}

function attachChildPayload(parentPayload, childPayload) {
  if (!childPayload?.field || !childPayload?.key) return
  if (!Array.isArray(parentPayload.children)) {
    parentPayload.children = []
  }
  parentPayload.children.push({
    k: childPayload.key,
    ...childPayload.field
  })
}

function attachEnumOptionChildren(parentKey, parentPayload, varsIndex) {
  if (!Array.isArray(parentPayload?.oneOf)) return
  for (const option of parentPayload.oneOf) {
    const optionValue = option?.v
    const matchedChildren = Array.from(varsIndex.values())
      .filter((payload) => {
        if (payload.__mounted) return false
        if (payload.field.if?.k !== parentKey) return false
        return String(payload.field.if?.eq ?? '') === String(optionValue ?? '')
      })
    if (!matchedChildren.length) continue
    
    // First map them to children array
    option.children = matchedChildren.map(payload => ({
      k: payload.key,
      ...payload.field
    }))
    
    // Then mark as mounted and remove the if condition from BOTH places
    for (let i = 0; i < matchedChildren.length; i++) {
      const child = matchedChildren[i]
      child.__mounted = true
      delete child.field.if
      delete option.children[i].if
    }
  }
}

function parseIfEqValue(rawValue) {
  if (rawValue === undefined || rawValue === null || rawValue === '') return undefined
  if (rawValue === 'true') return true
  if (rawValue === 'false') return false
  if (!isNaN(Number(rawValue)) && String(Number(rawValue)) === String(rawValue)) return Number(rawValue)
  return rawValue
}

function buildVarPayload(v) {
  const key = v._key
  if (!key) return null

  const field = {
    t: v.t,
    tp: v.tp,
    req: Boolean(v.req),
    note: v.note || ''
  }

  if (v.def !== '' && v.def !== null && v.def !== undefined) {
    field.def = v.def
  }

  if (v.tp === 'int') {
    if (v.min !== undefined && v.min !== null) field.min = v.min
    if (v.max !== undefined && v.max !== null) field.max = v.max
  } else if (v.tp === 'enum') {
    const options = cleanEnumOptions(v.oneOf)
    if (options.length) field.oneOf = options
  }

  if (v.if && v.if.k) {
    field.if = { k: v.if.k }
    const eqVal = parseIfEqValue(v.if.eq)
    if (eqVal !== undefined) {
      field.if.eq = eqVal
    }
  }

  return {
    key,
    field,
  }
}

function handleAddDependentVar(parentVar, eqValue = undefined) {
  if (!parentVar._key) {
    message.warning('请先填写父级参数的键名')
    return
  }
  const childVar = createVar(parentVar._key, eqValue)
  const index = varsList.value.indexOf(parentVar)
  if (index !== -1) {
    varsList.value.splice(index + 1, 0, childVar)
  } else {
    varsList.value.push(childVar)
  }
}

function buildTemplatePayload({ trimForPreview = false } = {}) {
  const result = {
    v: localData.value.v,
    id: localData.value.id,
    t: localData.value.t,
    d: localData.value.d,
    vars: {},
    tasks: (localData.value.tasks || []).map(task => ({
      k: task.k,
      t: task.t,
      fn: task.fn,
      args: Array.isArray(task.args) ? task.args.filter(Boolean) : []
    })),
    flows: (localData.value.flows || []).map(flow => ({
      k: flow.k,
      t: flow.t,
      g: Array.isArray(flow.g) ? flow.g.filter(Boolean) : [],
      steps: (flow.steps || []).map(step => ({
        k: step.k,
        task: step.task,
        args: step.args && typeof step.args === 'object' ? step.args : {},
        onFail: step.onFail || 'stop'
      }))
    }))
  }

  const payloadMap = new Map()

  for (const v of varsList.value) {
    const payload = buildVarPayload(v)
    if (payload) {
      payloadMap.set(payload.key, payload)
      result.vars[payload.key] = payload.field
    }
  }

  for (const payload of payloadMap.values()) {
    const conditionKey = payload.field.if?.k
    if (!conditionKey) continue
    const parentPayload = payloadMap.get(conditionKey)?.field
    if (!parentPayload) continue

    if (parentPayload.tp === 'enum') {
      continue
    }

    attachChildPayload(parentPayload, payload)
    payload.__mounted = true
    delete payload.field.if
  }

  for (const [payloadKey, payload] of payloadMap.entries()) {
    attachEnumOptionChildren(payloadKey, payload.field, payloadMap)
  }

  for (const payload of payloadMap.values()) {
    if (payload.__mounted) {
      delete result.vars[payload.key]
    }
  }

  if (!trimForPreview) {
    return result
  }

  return JSON.parse(JSON.stringify(result))
}

function validateTemplate() {
  if (!localData.value.id) {
    activeTab.value = 'basic'
    message.warning('模板 ID 不能为空')
    return false
  }

  const duplicatedVarKeys = varsList.value
    .map(item => item._key)
    .filter(Boolean)
    .filter((key, index, arr) => arr.indexOf(key) !== index)
  if (duplicatedVarKeys.length > 0) {
    activeTab.value = 'vars'
    message.warning(`存在重复参数键名: ${duplicatedVarKeys[0]}`)
    return false
  }

  const invalidTask = (localData.value.tasks || []).find(item => !item.k || !item.fn)
  if (invalidTask) {
    activeTab.value = 'tasks'
    message.warning('任务必须填写任务 Key 和 Lua 函数名')
    return false
  }

  const duplicatedTaskKeys = (localData.value.tasks || [])
    .map(item => item.k)
    .filter(Boolean)
    .filter((key, index, arr) => arr.indexOf(key) !== index)
  if (duplicatedTaskKeys.length > 0) {
    activeTab.value = 'tasks'
    message.warning(`存在重复任务 Key: ${duplicatedTaskKeys[0]}`)
    return false
  }

  const taskKeySet = new Set((localData.value.tasks || []).map(item => item.k).filter(Boolean))
  const varKeySet = new Set(flattenedVarOptions.value.map(item => item.value))
  for (const task of localData.value.tasks || []) {
    const procedure = getProcedureByName(task.fn)
    if (!procedure) {
      activeTab.value = 'tasks'
      message.warning(`任务引用了不存在的 Blockly 函数: ${task.fn}`)
      return false
    }
    if (!(procedure.args.length === 1 && procedure.args[0] === 'args')) {
      activeTab.value = 'tasks'
      message.warning(`任务只能绑定形如 function xxx(args) 的函数: ${task.fn}`)
      return false
    }
    for (const arg of task.args || []) {
      if (!varKeySet.has(arg)) {
        activeTab.value = 'tasks'
        message.warning(`任务变量不存在: ${arg}`)
        return false
      }
    }
  }

  for (const flow of localData.value.flows || []) {
    if (!flow.k) {
      activeTab.value = 'flows'
      message.warning('任务流必须填写 Key')
      return false
    }
    for (const globalArg of flow.g || []) {
      if (!varKeySet.has(globalArg)) {
        activeTab.value = 'flows'
        message.warning(`任务流全局参数不存在: ${globalArg}`)
        return false
      }
    }
    const stepKeys = new Set()
    for (const step of flow.steps || []) {
      if (!step.k || !step.task) {
        activeTab.value = 'flows'
        message.warning('任务流步骤必须填写步骤 ID 和任务')
        return false
      }
      if (stepKeys.has(step.k)) {
        activeTab.value = 'flows'
        message.warning(`任务流内存在重复步骤 ID: ${step.k}`)
        return false
      }
      stepKeys.add(step.k)
      if (!taskKeySet.has(step.task)) {
        activeTab.value = 'flows'
        message.warning(`任务流步骤引用了不存在的任务: ${step.task}`)
        return false
      }
    }
  }

  return true
}

function handleSave() {
  if (!validateTemplate()) return
  const result = buildTemplatePayload()
  if (state.templateEditorModalCallback.value) {
    state.templateEditorModalCallback.value(result)
  }
  visible.value = false
  message.success('已保存模板配置到拼图块')
}

function handleClose() {
  visible.value = false
}
</script>

<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    class="template-editor-modal-shell"
    style="width: 100vw; max-width: 100vw;"
    title="模板配置"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="template-editor-modal">
      <div class="template-editor-main">
        <div class="template-editor-summary">
          <div class="summary-item">
            <span class="summary-label">模板 ID</span>
            <span class="summary-value">{{ localData.id || '未命名模板' }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">参数</span>
            <n-tag size="small" round>{{ stats.vars }}</n-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">必填</span>
            <n-tag size="small" type="warning" round>{{ stats.requiredVars }}</n-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">任务</span>
            <n-tag size="small" type="info" round>{{ stats.tasks }}</n-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">任务流</span>
            <n-tag size="small" type="success" round>{{ stats.flows }}</n-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">步骤</span>
            <n-tag size="small" type="default" round>{{ stats.flowSteps }}</n-tag>
          </div>
          <div class="summary-item summary-item-grow">
            <span class="summary-label">可绑定函数</span>
            <n-tag size="small" type="primary" round>{{ procedureOptions.length }}</n-tag>
          </div>
        </div>

        <div class="template-editor-content">
          <n-tabs v-model:value="activeTab" type="segment" animated class="editor-tabs">
            <n-tab-pane name="basic" tab="基本信息">
              <div class="pane-scroll">
                <n-form :model="localData" label-placement="top" require-mark-placement="right-hanging">
                  <div class="form-grid cols-2">
                    <n-form-item label="模板 ID" path="id" required>
                      <n-input v-model:value="localData.id" placeholder="例如: daily_battle" />
                    </n-form-item>
                    <n-form-item label="版本" path="v">
                      <n-input-number v-model:value="localData.v" :min="1" style="width: 100%;" />
                    </n-form-item>
                  </div>
                  <n-form-item label="名称 (可选)" path="t">
                    <n-input v-model:value="localData.t" placeholder="显示给用户的名称" />
                  </n-form-item>
                  <n-form-item label="描述 (可选)" path="d">
                    <n-input type="textarea" v-model:value="localData.d" placeholder="模板的功能描述、使用场景、注意事项" :rows="5" />
                  </n-form-item>
                </n-form>
              </div>
            </n-tab-pane>

            <n-tab-pane name="vars" tab="变量与参数">
              <div class="pane-scroll">
                <div class="toolbar-row">
                  <n-input v-model:value="variableSearch" clearable placeholder="搜索参数键名 / 名称 / 说明 / 类型" class="toolbar-search" />
                  <n-space>
                    <n-button @click="varsList.push(createVar())">添加参数</n-button>
                    <n-button quaternary @click="varsList.forEach(item => { item._showAdvanced = true })">展开全部高级</n-button>
                  </n-space>
                </div>

                <n-alert v-if="!varsList.length" type="default" :show-icon="false" style="margin-bottom: 16px;">
                  还没有定义任何参数。参数会在模板执行时暴露给用户填写，也可供任务和任务流引用。
                </n-alert>

                <n-dynamic-input
                  v-model:value="varsList"
                  :on-create="() => createVar()"
                  :show-sort-button="true"
                  class="vars-dynamic-input"
                >
                  <template #create-button-default>添加参数</template>
                  <template #default="{ value }">
                    <div v-show="!variableSearch || filteredVarsList.includes(value)" class="editor-card editor-card-full" :class="{ 'is-dependent': value.if?.k }">
                      <div class="card-header">
                        <div class="card-title-wrap">
                          <div class="card-title-row">
                            <n-tag size="small" :type="value.req ? 'warning' : 'default'">{{ value.tp }}</n-tag>
                            <span class="card-title">{{ value.t || value._key || '未命名参数' }}</span>
                            <n-text depth="3">{{ value._key || '未设置键名' }}</n-text>
                          </div>
                          <n-text depth="3" class="card-subtitle">{{ value.note || '建议补充该参数的用途和填写说明。' }}</n-text>
                        </div>
                        <n-space>
                          <n-button size="small" quaternary @click="duplicateVar(value)">复制</n-button>
                          <n-button size="small" quaternary @click="value._showAdvanced = !value._showAdvanced">
                            {{ value._showAdvanced ? '收起高级' : '展开高级' }}
                          </n-button>
                        </n-space>
                      </div>

                      <div class="form-grid cols-3 compact-grid">
                        <n-input v-model:value="value._key" placeholder="参数键名 (英文)" />
                        <n-input v-model:value="value.t" placeholder="显示名称" />
                        <n-select v-model:value="value.tp" :options="tpOptions" @update:value="() => {
                          value.def = defaultValueForType(value.tp)
                          if (value.tp !== 'int') { value.min = undefined; value.max = undefined }
                          if (value.tp !== 'enum') { value.oneOf = [] }
                        }" />
                      </div>

                      <n-collapse :expanded-names="value._showAdvanced ? ['advanced'] : []" class="ghost-collapse">
                        <n-collapse-item name="advanced">
                          <template #header>
                            <span></span>
                          </template>
                          <div class="advanced-panel">
                            <div v-if="value.if && value.if.k" class="sub-panel" style="margin-top: 0; margin-bottom: 12px; background: var(--n-color-modal); border-left: 3px solid var(--n-primary-color);">
                              <div class="sub-panel-title" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0;">
                                <span>受控关联参数</span>
                                <n-button size="small" type="error" quaternary @click="value.if = null">取消关联</n-button>
                              </div>
                              <n-text depth="3" style="display: block; margin-top: 4px;">
                                当参数 <n-tag size="small" type="info">{{ value.if.k }}</n-tag>
                                的值为 <n-tag size="small" type="warning">{{ value.if.eq !== '' && value.if.eq !== undefined ? String(value.if.eq) : '(任意)' }}</n-tag>
                                时，该参数才会显示并生效。
                              </n-text>
                            </div>

                            <div class="form-grid cols-2 compact-grid">
                              <div class="inline-switch-field">
                                <n-switch v-model:value="value.req" />
                                <span>必填参数</span>
                              </div>
                              <n-input v-model:value="value.note" placeholder="提示说明 (note)" />
                            </div>

                            <div v-if="value.tp === 'int'" class="form-grid cols-3 compact-grid">
                              <n-input-number v-model:value="value.def" placeholder="默认值" style="width: 100%;" />
                              <n-input-number v-model:value="value.min" placeholder="最小值" style="width: 100%;" />
                              <n-input-number v-model:value="value.max" placeholder="最大值" style="width: 100%;" />
                            </div>
                            <div v-else-if="value.tp === 'str' || value.tp === 'path'" class="form-grid cols-1 compact-grid">
                              <n-input v-model:value="value.def" placeholder="默认值" />
                            </div>
                            <div v-else-if="value.tp === 'bool'" class="inline-switch-field panel-block">
                              <n-switch v-model:value="value.def" />
                              <span>默认状态</span>
                            </div>

                            <div v-if="value.tp === 'enum'" class="sub-panel">
                              <div class="sub-panel-header">
                                <div>
                                  <div class="sub-panel-title">枚举选项</div>
                                </div>
                              </div>
                              <n-dynamic-input v-model:value="value.oneOf" :on-create="createEnumOption" class="enum-options-dynamic-input">
                                <template #default="{ value: opt }">
                                  <div class="child-card enum-option-card">
                                    <div class="form-grid cols-2 compact-grid" style="margin-bottom: 0;">
                                      <n-input v-model:value="opt.v" placeholder="值 (value)" />
                                      <n-input v-model:value="opt.t" placeholder="显示名称 (t)" />
                                    </div>
                                    <div style="margin-top: 8px;">
                                      <n-button size="small" dashed @click="handleAddDependentVar(value, opt.v)">以此选项作为条件添加关联参数</n-button>
                                    </div>
                                  </div>
                                </template>
                              </n-dynamic-input>
                              <div class="form-grid cols-1 compact-grid" style="margin-top: 12px;">
                                <n-input v-model:value="value.def" placeholder="默认值，填写 oneOf 中的 v" />
                              </div>
                            </div>

                            <div v-if="value.tp === 'bool'" style="margin-top: 12px;">
                              <n-button dashed @click="handleAddDependentVar(value, 'true')">以此开关开启作为条件添加关联参数</n-button>
                            </div>
                          </div>
                        </n-collapse-item>
                      </n-collapse>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>

            <n-tab-pane name="tasks" tab="任务">
              <div class="pane-scroll">
                <div class="toolbar-row">
                  <n-button @click="refreshProcedureDefinitions()">刷新函数列表</n-button>
                </div>

                <n-alert v-if="!procedureOptions.length" type="warning" :show-icon="false" style="margin-bottom: 16px;">
                  当前 Blockly 工作区没有可绑定的函数。请先创建至少一个“函数参数 args”的 有返回函数 或 无返回函数。
                </n-alert>

                <n-dynamic-input v-model:value="localData.tasks" :on-create="createTask" :show-sort-button="true">
                  <template #create-button-default>添加任务</template>
                  <template #default="{ value }">
                    <div class="editor-card task-editor-card">
                      <div class="task-editor-grid">
                        <n-input v-model:value="value.k" placeholder="任务 Key，例如 battle" />
                        <n-input v-model:value="value.t" placeholder="任务名称，例如 执行战斗" />
                        <n-select
                          v-model:value="value.fn"
                          :options="procedureOptions"
                          clearable
                          filterable
                          placeholder="选择 Blockly 函数"
                          @update:value="() => handleTaskFunctionChange(value)"
                        />
                      </div>

                      <div class="field-block">
                        <div class="field-label">任务变量</div>
                        <div class="picker-summary-row">
                          <div class="picker-summary-text">已选择 {{ value.args?.length || 0 }} 项</div>
                          <n-button size="small" @click="openTaskVarPicker(value)">选择任务变量</n-button>
                        </div>
                        <div class="task-selected-tags" v-if="value.args?.length">
                          <n-tag v-for="arg in value.args" :key="arg" size="small" type="info" round>{{ arg }}</n-tag>
                        </div>
                      </div>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>

            <n-tab-pane name="flows" tab="任务流">
              <div class="pane-scroll">
                <n-dynamic-input v-model:value="localData.flows" :on-create="createFlow" :show-sort-button="true">
                  <template #create-button-default>添加任务流</template>
                  <template #default="{ value }">
                    <div class="editor-card flow-editor-card">
                      <div class="form-grid cols-2 compact-grid">
                        <n-input v-model:value="value.k" placeholder="任务流 Key (主流程一般为 main)" />
                        <n-input v-model:value="value.t" placeholder="任务流名称 (可选)" />
                      </div>

                      <div class="field-block">
                        <div class="field-label">任务流全局参数</div>
                        <div class="picker-summary-row">
                          <div class="picker-summary-text">已选择 {{ value.g?.length || 0 }} 项</div>
                          <n-button size="small" @click="openFlowGlobalPicker(value)">选择任务流全局参数</n-button>
                        </div>
                        <div class="task-selected-tags" v-if="value.g?.length">
                          <n-tag v-for="globalArg in value.g" :key="globalArg" size="small" type="success" round>{{ globalArg }}</n-tag>
                        </div>
                      </div>

                      <n-divider style="margin: 18px 0 14px;">任务流步骤</n-divider>
                      <n-dynamic-input v-model:value="value.steps" :on-create="createFlowStep" :show-sort-button="true">
                        <template #default="{ value: step }">
                          <div class="child-card flow-step-card flow-step-card-wide">
                            <div class="step-topbar">
                              <div class="card-title-row">
                                <n-tag size="small">Step</n-tag>
                                <span class="card-title">{{ step.k || '未命名步骤' }}</span>
                              </div>
                              <n-button size="small" quaternary @click="fillArgsFromTask(step)">自动生成步骤默认值</n-button>
                            </div>
                            <div class="flow-step-grid compact-grid">
                              <n-input v-model:value="step.k" placeholder="步骤 ID" />
                              <n-select
                                v-model:value="step.task"
                                :options="taskOptions"
                                filterable
                                clearable
                                placeholder="搜索选择任务"
                                @update:value="() => handleStepTaskChange(step)"
                              />
                              <n-select v-model:value="step.onFail" :options="onFailOptions" />
                            </div>
                            <div class="field-block">
                              <div class="field-label">步骤默认值</div>
                              <div class="picker-summary-row">
                                <div class="picker-summary-text">已配置 {{ Object.keys(step.args || {}).length }} 项</div>
                                <n-button size="small" :disabled="!step.task" @click="openStepArgsPicker(value, step)">配置步骤默认值</n-button>
                              </div>
                              <div class="task-selected-tags" v-if="Object.keys(step.args || {}).length">
                                <n-tag v-for="[argKey, argValue] in Object.entries(step.args || {})" :key="argKey" size="small" type="warning" round>
                                  {{ argKey }} = {{ formatValuePreview(argValue) }}
                                </n-tag>
                              </div>
                            </div>
                          </div>
                        </template>
                      </n-dynamic-input>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </div>

      <div class="template-editor-preview">
        <div class="preview-header">
          <div>
            <div class="preview-title">实时预览</div>
            <n-text depth="3">保存前可直接检查最终 JSON 结构</n-text>
          </div>
        </div>
        <div class="preview-scroll-shell">
          <n-scrollbar x-scrollable y-scrollable style="height: 70vh; width: 100%;">
            <pre class="preview-code">{{ templatePreview }}</pre>
          </n-scrollbar>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="space-between" align="center" style="width: 100%;">
        <n-text depth="3">模板定义会写入 Blockly 块的隐藏 JSON 字段中</n-text>
        <n-space>
          <n-button @click="handleClose">取消</n-button>
          <n-button type="primary" @click="handleSave">保存配置</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="pickerState.show"
    preset="card"
    style="width: 760px; max-width: 92vw;"
    :title="pickerState.title"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="picker-dialog-body">
      <n-alert v-if="pickerState.summary" type="info" :show-icon="false" style="margin-bottom: 16px;">
        {{ pickerState.summary }}
      </n-alert>
      <n-input
        v-model:value="pickerState.search"
        clearable
        placeholder="搜索键名 / 名称 / 来源"
        style="margin-bottom: 16px;"
      />
      <div class="picker-dialog-list">
        <div v-if="!pickerFilteredOptions.length" class="picker-empty-text">没有匹配项</div>
        <div v-else class="picker-option-grid">
          <label v-for="item in pickerFilteredOptions" :key="item.value" class="picker-option-card">
            <input v-model="pickerState.value" type="checkbox" :value="item.value" class="picker-option-checkbox" />
            <div class="picker-option-content">
              <div class="picker-option-title">{{ item.label }}</div>
              <n-text depth="3">{{ item.desc || '顶层变量' }}</n-text>
            </div>
          </label>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="closePicker">取消</n-button>
        <n-button type="primary" @click="confirmPicker">确认</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="stepArgEditorState.show"
    preset="card"
    style="width: 920px; max-width: 96vw;"
    title="配置步骤默认值"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="step-arg-editor-body">
      <n-alert type="info" :show-icon="false" style="margin-bottom: 16px;">
        按变量类型自动推导输入方式：文本参数填写字符串，布尔参数使用开关，整数参数使用数字输入，枚举参数直接选择枚举项。
      </n-alert>
      <div class="step-arg-editor-list">
        <div v-for="row in stepArgEditorState.rows" :key="row.key" class="step-arg-editor-row">
          <div class="step-arg-editor-enable">
            <input v-model="stepArgEditorState.selectedKeys" type="checkbox" :value="row.key" class="picker-option-checkbox" />
          </div>
          <div class="step-arg-editor-key">
            <div>{{ row.label }}</div>
            <n-text depth="3">{{ row.key }}</n-text>
          </div>
          <div class="step-arg-editor-inputs">
            <template v-if="row.editorType === 'bool'">
              <div class="inline-switch-field step-arg-inline-editor">
                <n-switch v-model:value="row.value" />
                <span>{{ row.value ? 'true' : 'false' }}</span>
              </div>
            </template>
            <template v-else-if="row.editorType === 'number'">
              <n-input-number v-model:value="row.value" style="width: 100%;" placeholder="填写数字默认值" />
            </template>
            <template v-else-if="row.editorType === 'enum'">
              <n-select
                v-model:value="row.value"
                :options="enumOptionsForKey(row.key)"
                filterable
                clearable
                placeholder="选择枚举默认值"
              />
            </template>
            <template v-else>
              <div class="step-arg-text-mode-grid">
                <n-input
                  v-if="row.sourceMode === 'literal'"
                  v-model:value="row.value"
                  placeholder="填写字符串默认值，例如 2-1"
                />
                <n-select
                  v-else
                  v-model:value="row.value"
                  :options="stepArgSourceOptions"
                  filterable
                  clearable
                  placeholder="选择模板变量作为默认值来源"
                />
                <n-button quaternary size="small" @click="row.sourceMode = row.sourceMode === 'literal' ? 'var' : 'literal'">
                  {{ row.sourceMode === 'literal' ? '改为引用模板变量' : '改为直接填写常量' }}
                </n-button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="closeStepArgEditor">取消</n-button>
        <n-button type="primary" @click="confirmStepArgEditor">确认</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
:global(.template-editor-modal-shell .n-card) {
  width: 100%;
  display: flex;
  flex-direction: column;
}

:global(.template-editor-modal-shell .n-card__content) {
  overflow: auto;
}

.template-editor-modal {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
}

.template-editor-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.template-editor-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  background: var(--n-color-embedded);
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-item-grow {
  margin-left: auto;
}

.summary-label {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.summary-value {
  font-weight: 600;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-editor-content {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  padding: 16px;
  overflow: hidden;
}

.editor-tabs,
.pane-scroll {
  height: 100%;
}

.pane-scroll {
  overflow: auto;
  padding-right: 4px;
}

.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.toolbar-search {
  flex: 1;
  width: 100%;
  max-width: none;
}

.toolbar-alert {
  flex: 1;
}

.editor-card {
  border: 1px solid var(--n-border-color);
  padding: 16px;
  border-radius: 10px;
  background: var(--n-color-embedded);
}

.editor-card-full,
.task-editor-card,
.flow-editor-card {
  width: 100%;
}

.is-dependent {
  margin-left: 24px;
  width: calc(100% - 24px) !important;
  border-left: 4px solid var(--n-primary-color);
}

.vars-dynamic-input :deep(.n-dynamic-input-item) {
  width: 100%;
}

.vars-dynamic-input :deep(.n-dynamic-input-item__content) {
  flex: 1;
  min-width: 0;
}

.vars-dynamic-input :deep(.n-dynamic-input-item__action) {
  flex: 0 0 auto;
}

.enum-options-dynamic-input :deep(.n-dynamic-input-item) {
  width: 100%;
}

.enum-options-dynamic-input :deep(.n-dynamic-input-item__content) {
  flex: 1;
  min-width: 0;
}

.enum-options-dynamic-input :deep(.n-dynamic-input-item__action) {
  flex: 0 0 auto;
}

.enum-option-card {
  width: 100%;
}

.task-editor-grid {
  display: grid;
  grid-template-columns: 180px 220px minmax(260px, 1fr);
  gap: 12px;
}

.child-card {
  border: 1px dashed var(--n-border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--n-color);
}

.flow-step-card {
  background: var(--n-color-embedded);
}

.flow-step-card-wide {
  width: 100%;
}

.card-header,
.step-topbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.card-title-wrap {
  min-width: 0;
}

.card-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.card-title {
  font-weight: 600;
}

.card-subtitle {
  display: block;
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid.cols-1 {
  grid-template-columns: minmax(0, 1fr);
}

.form-grid.cols-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid.cols-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.compact-grid {
  margin-bottom: 12px;
}

.inline-switch-field {
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  background: var(--n-color);
}

.panel-block {
  margin-bottom: 12px;
}

.advanced-panel {
  padding-top: 8px;
}

.sub-panel {
  margin-top: 8px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--n-color);
}

.nested-panel {
  background: var(--n-color-embedded);
}

.sub-panel-header {
  margin-bottom: 12px;
}

.sub-panel-title,
.field-label,
.preview-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.field-block {
  margin-top: 12px;
}

.flow-step-grid {
  display: grid;
  grid-template-columns: 180px minmax(220px, 1fr) 160px;
  gap: 12px;
}

.picker-summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.picker-summary-text {
  font-size: 13px;
  color: var(--n-text-color-3);
}

.task-selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.template-editor-preview {
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  padding: 16px;
  background: var(--n-color);
  min-width: 0;
  min-height: 0;
  align-self: start;
  position: sticky;
  top: 0;
  overflow: hidden;
}

.preview-header {
  margin-bottom: 12px;
}

.preview-scroll-shell {
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.preview-code {
  display: inline-block;
  margin: 0;
  white-space: pre;
  word-break: normal;
  overflow-wrap: normal;
  min-width: max-content;
  padding-right: 12px;
  font-size: 12px;
  line-height: 1.6;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.picker-dialog-body {
  min-height: 320px;
}

.picker-dialog-list {
  max-height: 52vh;
  overflow: auto;
}

.picker-empty-text {
  padding: 24px;
  text-align: center;
  color: var(--n-text-color-3);
}

.picker-option-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}

.picker-option-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color-embedded);
  cursor: pointer;
}

.picker-option-checkbox {
  margin-top: 3px;
}

.picker-option-content {
  min-width: 0;
}

.picker-option-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.step-arg-editor-body {
  min-height: 320px;
}

.step-arg-editor-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 56vh;
  overflow: auto;
}

.step-arg-editor-row {
  display: grid;
  grid-template-columns: 42px 180px minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color-embedded);
}

.step-arg-editor-enable {
  padding-top: 8px;
}

.step-arg-editor-key {
  padding-top: 6px;
}

.step-arg-editor-inputs {
  min-width: 0;
}

.step-arg-inline-editor {
  width: 100%;
}

.step-arg-text-mode-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px auto;
  gap: 12px;
}

.ghost-collapse :deep(.n-collapse-item__header) {
  display: none;
}

.ghost-collapse :deep(.n-collapse-item__content-inner) {
  padding-top: 0 !important;
}

@media (max-width: 1280px) {
  .template-editor-modal {
    grid-template-columns: 1fr;
  }

  .template-editor-preview {
    position: static;
    max-height: 320px;
  }
}

@media (max-width: 960px) {
  .task-editor-grid,
  .flow-step-grid,
  .step-arg-editor-row,
  .step-arg-text-mode-grid,
  .form-grid.cols-2,
  .form-grid.cols-3,
  .toolbar-row,
  .card-header,
  .step-topbar,
  .picker-summary-row {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .template-editor-summary {
    gap: 8px;
  }

  .summary-item-grow {
    margin-left: 0;
  }

  .toolbar-search {
    max-width: none;
    width: 100%;
  }

  .picker-option-grid {
    grid-template-columns: 1fr;
  }
}
</style>
