export function createEmptyTemplate() {
  return {
    v: 1,
    id: '',
    t: '',
    d: '',
    vars: {},
    tasks: [],
    flows: [],
  }
}

export function createTemplateVariable() {
  return {
    _key: '',
    t: '',
    tp: 'str',
    ui: '',
    def: '',
    req: false,
    note: '',
    min: undefined,
    max: undefined,
    oneOf: [],
    if: null,
    _showAdvanced: false,
  }
}

export function createTemplateTask() {
  return { k: '', t: '', fn: '', args: [], _fnArgs: ['args'] }
}

export function taskArgKey(arg) {
  return typeof arg === 'string' ? arg : String(arg?.k || '')
}

export function taskArgKeys(args) {
  return (args || []).map(taskArgKey).filter(Boolean)
}

export function taskArgCondition(arg) {
  return typeof arg === 'string' || !arg?.if?.k ? null : arg.if
}

const TASK_ARG_CONDITION_OPERATORS = ['in', 'gt', 'gte', 'lt', 'lte', 'ne', 'eq']
const TASK_ARG_CONDITION_OPERATORS_BY_TYPE = {
  bool: ['eq'],
  enum: ['eq', 'ne', 'in'],
  int: ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
  num: ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'],
  str: ['eq', 'ne', 'in'],
  json: ['eq', 'ne'],
}

export function taskArgConditionOperatorsForType(type) {
  return [...(TASK_ARG_CONDITION_OPERATORS_BY_TYPE[type] || TASK_ARG_CONDITION_OPERATORS_BY_TYPE.str)]
}

function resolveTaskArgConditionOperator(condition) {
  if (!condition) return 'eq'
  if ((Array.isArray(condition.in) && condition.in.length) || typeof condition.in === 'string') return 'in'
  const scalarOperator = TASK_ARG_CONDITION_OPERATORS
    .filter(operator => operator !== 'in')
    .find(operator => Object.prototype.hasOwnProperty.call(condition, operator))
  if (scalarOperator) return scalarOperator
  return Object.prototype.hasOwnProperty.call(condition, 'in') ? 'in' : 'eq'
}

export function taskArgConditionOperator(arg) {
  return resolveTaskArgConditionOperator(taskArgCondition(arg))
}

export function updateTaskArgCondition(args, argKey, condition) {
  return (args || []).map((arg) => {
    if (taskArgKey(arg) !== argKey) return arg
    if (!condition?.k) return argKey
    const operator = TASK_ARG_CONDITION_OPERATORS.find(item => Object.prototype.hasOwnProperty.call(condition, item))
    return { k: argKey, if: { k: condition.k, ...(operator ? { [operator]: condition[operator] } : {}) } }
  })
}

export function mergeTaskArgSelection(args, selectedKeys) {
  const existing = new Map((args || []).map(arg => [taskArgKey(arg), arg]))
  return (selectedKeys || []).map(key => existing.get(key) || key)
}

export function buildTaskArgTreeRows(args) {
  const nodes = (args || [])
    .map((arg, index) => ({
      arg,
      key: taskArgKey(arg),
      condition: taskArgCondition(arg),
      index,
      children: [],
    }))
    .filter(node => node.key)
  const nodeByKey = new Map(nodes.map(node => [node.key, node]))
  const roots = []

  for (const node of nodes) {
    const parent = node.condition?.k ? nodeByKey.get(node.condition.k) : null
    if (!parent || parent === node) roots.push(node)
    else parent.children.push(node)
  }

  const rows = []
  const visited = new Set()
  const appendNode = (node, depth) => {
    if (visited.has(node.key)) return
    visited.add(node.key)
    rows.push({
      arg: node.arg,
      key: node.key,
      condition: node.condition,
      depth,
      detached: depth === 0 && Boolean(node.condition?.k),
    })
    node.children
      .sort((left, right) => left.index - right.index)
      .forEach(child => appendNode(child, depth + 1))
  }

  roots
    .sort((left, right) => left.index - right.index)
    .forEach(root => appendNode(root, 0))
  // Invalid cyclic relationships have no natural root. Keep every parameter editable.
  nodes.forEach(node => appendNode(node, 0))
  return rows
}

export function createTemplateFlow() {
  return { k: '', t: '', g: [], steps: [] }
}

export function createTemplateFlowStep() {
  return { k: '', task: '', args: {}, onSuccess: 'continue', successGoto: '', onFail: 'stop', goto: '' }
}

export function createStepArgBinding(source = 'var', value = '') {
  if (source === 'literal') return { $bind: 'literal', value }
  return { $bind: 'var', key: String(value || '') }
}

export function normalizeStepArgBinding(value) {
  if (value && typeof value === 'object' && value.$bind === 'var') {
    return createStepArgBinding('var', value.key)
  }
  if (value && typeof value === 'object' && value.$bind === 'literal') {
    return createStepArgBinding('literal', value.value)
  }
  // Legacy step values were plain literals. Keep that behavior when editing old templates.
  return createStepArgBinding('literal', value)
}

export function createEnumOption() {
  return { v: '', t: '', children: [] }
}

function defaultValueForType(type) {
  if (type === 'bool') return false
  if (type === 'int' || type === 'num') return null
  return ''
}

function normalizeIfValue(value) {
  if (value === undefined || value === null || value === '') return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function normalizeEnumOption(option) {
  if (option && typeof option === 'object') {
    return { v: option.v ?? '', t: option.t ?? '' }
  }
  return { v: option ?? '', t: '' }
}

function normalizeVariable(key, value = {}) {
  const type = value.tp || 'str'
  return {
    _key: key !== undefined ? key : (value.k || ''),
    t: value.t || '',
    tp: type,
    ui: type === 'str' ? (value.ui || '') : '',
    def: value.def !== undefined ? value.def : defaultValueForType(type),
    req: Boolean(value.req),
    note: value.note || '',
    min: value.min,
    max: value.max,
    oneOf: Array.isArray(value.oneOf) ? value.oneOf.map(normalizeEnumOption) : [],
    if: value.if?.k ? { k: value.if.k, eq: normalizeIfValue(value.if.eq) } : null,
    _showAdvanced: false,
  }
}

function normalizeTask(task = {}) {
  return {
    k: task.k || '',
    t: task.t || '',
    fn: task.fn || '',
    args: Array.isArray(task.args) ? task.args.map((arg) => {
      const key = taskArgKey(arg)
      const condition = taskArgCondition(arg)
      return condition ? { k: key, if: { ...condition } } : key
    }).filter(taskArgKey) : [],
    _fnArgs: ['args'],
  }
}

export function flattenParsedVars(varsObject) {
  const result = []

  // The form edits one flat sequence even though persisted variables can be nested.
  function traverse(key, value, implicitIf) {
    const normalized = normalizeVariable(key, value)
    if (!normalized.if && implicitIf) {
      normalized.if = { k: implicitIf.k, eq: implicitIf.eq !== undefined ? String(implicitIf.eq) : '' }
    }
    if (normalized.if) normalized._showAdvanced = true
    result.push(normalized)

    if (Array.isArray(value.children)) {
      for (const child of value.children) {
        const eqValue = value.tp === 'bool' ? 'true' : ''
        traverse(child.k || '', child, { k: key, eq: eqValue })
      }
    }
    if (Array.isArray(value.oneOf)) {
      for (const option of value.oneOf) {
        for (const child of option.children || []) {
          traverse(child.k || '', child, { k: key, eq: option.v })
        }
      }
    }
  }

  for (const [key, value] of Object.entries(varsObject || {})) {
    traverse(key, value, null)
  }
  return result
}

export function normalizeTemplateEditorData(data = {}) {
  const localData = {
    v: data.v || 1,
    id: data.id || '',
    t: data.t || '',
    d: data.d || '',
    tasks: Array.isArray(data.tasks) ? data.tasks.map(normalizeTask) : [],
    flows: Array.isArray(data.flows) ? data.flows.map(flow => ({
      k: flow.k || '',
      t: flow.t || '',
      g: Array.isArray(flow.g) ? [...flow.g] : [],
      steps: Array.isArray(flow.steps) ? flow.steps.map(step => ({
        k: step.k || '',
        task: step.task || '',
        args: step.args && typeof step.args === 'object' ? { ...step.args } : {},
        onSuccess: step.onSuccess || 'continue',
        successGoto: step.successGoto || '',
        onFail: step.onFail || 'stop',
        goto: step.goto || '',
      })) : [],
    })) : [],
  }
  const varsList = flattenParsedVars(data.vars || {})
  const legacyConditions = new Map(varsList.filter(variable => variable.if?.k).map(variable => [variable._key, variable.if]))
  for (const task of localData.tasks) {
    const keys = new Set(taskArgKeys(task.args))
    task.args = task.args.map((arg) => {
      if (taskArgCondition(arg)) return arg
      const key = taskArgKey(arg)
      const condition = legacyConditions.get(key)
      return condition?.k && keys.has(condition.k) ? { k: key, if: { ...condition } } : key
    })
  }
  // Parameter definitions no longer own presentation or activation relationships.
  for (const variable of varsList) variable.if = null
  return { localData, varsList }
}

function mapUniqueValues(values, from, to) {
  const result = []
  const seen = new Set()
  for (const value of values || []) {
    const mapped = String(value === from ? to : value || '').trim()
    if (!mapped || seen.has(mapped)) continue
    seen.add(mapped)
    result.push(mapped)
  }
  return result
}

export function renameVariableReferences({ varsList, localData, from, to }) {
  const oldKey = String(from || '').trim()
  const newKey = String(to || '').trim()
  if (!oldKey || oldKey === newKey) return

  for (const task of localData?.tasks || []) {
    task.args = (task.args || []).map((arg) => {
      const key = taskArgKey(arg)
      const condition = taskArgCondition(arg)
      const nextKey = key === oldKey ? newKey : key
      if (!condition) return nextKey
      const nextCondition = { ...condition, k: condition.k === oldKey ? newKey : condition.k }
      return { k: nextKey, if: nextCondition }
    })
  }
  for (const flow of localData?.flows || []) {
    flow.g = mapUniqueValues(flow.g, oldKey, newKey)
    for (const step of flow.steps || []) {
      if (!step?.args || typeof step.args !== 'object') continue
      const nextArgs = {}
      for (const [key, value] of Object.entries(step.args)) {
        const mappedKey = key === oldKey ? newKey : key
        if (!mappedKey || Object.prototype.hasOwnProperty.call(nextArgs, mappedKey)) continue
        if (value && typeof value === 'object' && value.$bind === 'var') {
          nextArgs[mappedKey] = { ...value, key: value.key === oldKey ? newKey : value.key }
        } else {
          nextArgs[mappedKey] = value === oldKey ? newKey : value
        }
      }
      step.args = nextArgs
    }
  }
}

export function countVariableReferences({ varsList, localData, key }) {
  const targetKey = String(key || '').trim()
  if (!targetKey) return 0
  let count = 0
  for (const task of localData?.tasks || []) {
    for (const arg of task.args || []) {
      if (taskArgKey(arg) === targetKey) count += 1
      if (taskArgCondition(arg)?.k === targetKey) count += 1
    }
  }
  for (const flow of localData?.flows || []) {
    count += (flow.g || []).filter(item => item === targetKey).length
    for (const step of flow.steps || []) {
      for (const [argKey, value] of Object.entries(step.args || {})) {
        if (argKey === targetKey) count += 1
        if (value?.$bind === 'var' && value.key === targetKey) count += 1
      }
    }
  }
  return count
}

export function removeVariableReferences({ varsList, localData, key }) {
  const targetKey = String(key || '').trim()
  if (!targetKey) return
  for (const task of localData?.tasks || []) {
    task.args = (task.args || [])
      .filter(arg => taskArgKey(arg) !== targetKey)
      .map(arg => taskArgCondition(arg)?.k === targetKey ? taskArgKey(arg) : arg)
  }
  for (const flow of localData?.flows || []) {
    flow.g = (flow.g || []).filter(item => item !== targetKey)
    for (const step of flow.steps || []) {
      const nextArgs = {}
      for (const [argKey, value] of Object.entries(step.args || {})) {
        if (argKey === targetKey) continue
        if (value?.$bind === 'var' && value.key === targetKey) continue
        nextArgs[argKey] = value
      }
      step.args = nextArgs
    }
  }
}

export function countTaskReferences(localData, key) {
  const targetKey = String(key || '').trim()
  if (!targetKey) return 0
  return (localData?.flows || []).reduce(
    (total, flow) => total + (flow.steps || []).filter(step => step.task === targetKey).length,
    0,
  )
}

export function removeTaskReferences(localData, key) {
  const targetKey = String(key || '').trim()
  if (!targetKey) return
  for (const flow of localData?.flows || []) {
    const removedStepKeys = new Set(
      (flow.steps || []).filter(step => step.task === targetKey).map(step => step.k).filter(Boolean),
    )
    flow.steps = (flow.steps || []).filter(step => step.task !== targetKey)
    for (const step of flow.steps) {
      if (step.onSuccess === 'goto' && removedStepKeys.has(step.successGoto)) {
        step.onSuccess = 'continue'
        step.successGoto = ''
      }
      if (step.onFail === 'goto' && removedStepKeys.has(step.goto)) {
        step.onFail = 'stop'
        step.goto = ''
      }
    }
  }
}

export function validateTemplateDraft(localData, varsList, { procedureNames = null } = {}) {
  const errors = []
  const variableKeys = (varsList || []).map(item => String(item?._key || '').trim())
  const variablesByKey = new Map((varsList || []).map(item => [String(item?._key || '').trim(), item]))
  const taskKeys = (localData?.tasks || []).map(item => String(item?.k || '').trim())
  const flowKeys = (localData?.flows || []).map(item => String(item?.k || '').trim())

  const addKeyErrors = (keys, label) => {
    const seen = new Set()
    keys.forEach((key, index) => {
      if (!key) {
        errors.push(`${label} ${index + 1} 缺少 Key`)
        return
      }
      if (seen.has(key)) errors.push(`${label} Key 重复：${key}`)
      seen.add(key)
    })
  }
  addKeyErrors(variableKeys, '参数')
  addKeyErrors(taskKeys, '任务')
  addKeyErrors(flowKeys, '任务流')

  const variableKeySet = new Set(variableKeys.filter(Boolean))
  const taskKeySet = new Set(taskKeys.filter(Boolean))
  const procedureNameSet = Array.isArray(procedureNames) ? new Set(procedureNames.filter(Boolean)) : null
  for (const task of localData?.tasks || []) {
    const taskLabel = task.k || '未命名任务'
    const functionName = String(task.fn || '').trim()
    if (!functionName) {
      errors.push(`任务 ${taskLabel} 未选择 Blockly 函数`)
    } else if (procedureNameSet && !procedureNameSet.has(functionName)) {
      errors.push(`任务 ${taskLabel} 引用的 Blockly 函数不存在：${functionName}`)
    }
    const argKeys = taskArgKeys(task.args)
    for (const argKey of argKeys) {
      if (!variableKeySet.has(argKey)) errors.push(`任务 ${taskLabel} 引用了不存在的参数：${argKey}`)
    }
    for (const arg of task.args || []) {
      const argKey = taskArgKey(arg)
      const condition = taskArgCondition(arg)
      if (!condition) continue
      if (condition.k === argKey) errors.push(`任务 ${taskLabel} 的参数 ${argKey} 不能依赖自身`)
      if (!argKeys.includes(condition.k)) errors.push(`任务 ${taskLabel} 的参数 ${argKey} 依赖了任务未选择的参数：${condition.k}`)
      const operator = resolveTaskArgConditionOperator(condition)
      const parent = variablesByKey.get(condition.k)
      const parentType = parent?.tp || 'str'
      if (!taskArgConditionOperatorsForType(parentType).includes(operator)) {
        errors.push(`任务 ${taskLabel} 的参数 ${argKey} 使用了不适用于 ${parentType} 的条件：${operator}`)
      }
      if (['gt', 'gte', 'lt', 'lte'].includes(operator)) {
        const value = condition[operator]
        if (value === '' || value === null || typeof value === 'undefined' || !Number.isFinite(Number(value))) {
          errors.push(`任务 ${taskLabel} 的参数 ${argKey} 的数值比较条件必须是有效数字`)
        }
      }
      if (Object.prototype.hasOwnProperty.call(condition, 'in')) {
        try {
          const values = Array.isArray(condition.in) ? condition.in : JSON.parse(condition.in)
          if (!Array.isArray(values)) errors.push(`任务 ${taskLabel} 的参数 ${argKey} 的“在集合中”条件必须是 JSON 数组`)
        } catch {
          errors.push(`任务 ${taskLabel} 的参数 ${argKey} 的“在集合中”条件必须是 JSON 数组`)
        }
      }
    }
  }
  for (const flow of localData?.flows || []) {
    for (const key of flow.g || []) {
      if (!variableKeySet.has(key)) errors.push(`任务流 ${flow.k || '未命名任务流'} 引用了不存在的参数：${key}`)
    }
    const stepKeys = (flow.steps || []).map(step => String(step?.k || '').trim())
    addKeyErrors(stepKeys, `任务流 ${flow.k || '未命名任务流'} 的步骤`)
    const stepKeySet = new Set(stepKeys.filter(Boolean))
    for (const step of flow.steps || []) {
      const stepLabel = step.k || '未命名步骤'
      const task = (localData?.tasks || []).find(item => item.k === step.task)
      if (!step.task || !taskKeySet.has(step.task)) {
        errors.push(`步骤 ${stepLabel} 引用了不存在的任务：${step.task || '未选择'}`)
      }
      const taskArgKeySet = new Set(taskArgKeys(task?.args))
      for (const [argKey, value] of Object.entries(step.args || {})) {
        if (!taskArgKeySet.has(argKey)) errors.push(`步骤 ${stepLabel} 覆盖了任务未声明的参数：${argKey}`)
        if (value?.$bind === 'var' && !variableKeySet.has(value.key)) {
          errors.push(`步骤 ${stepLabel} 绑定了不存在的参数：${value.key || '未选择'}`)
        }
        if (value?.$bind === 'var' && !(flow.g || []).includes(value.key)) {
          errors.push(`步骤 ${stepLabel} 绑定了任务流未选择的参数：${value.key || '未选择'}`)
        }
      }
      if (step.onSuccess === 'goto' && !stepKeySet.has(step.successGoto)) {
        errors.push(`步骤 ${stepLabel} 的成功跳转目标不存在：${step.successGoto || '未选择'}`)
      }
      if (step.onFail === 'goto' && !stepKeySet.has(step.goto)) {
        errors.push(`步骤 ${stepLabel} 的失败跳转目标不存在：${step.goto || '未选择'}`)
      }
    }
  }
  return [...new Set(errors)]
}

function cleanEnumOptions(options) {
  return (options || [])
    .map(option => ({ v: option?.v ?? '', t: option?.t ?? '' }))
    .filter(option => option.v !== '')
}

function parseConditionScalar(value) {
  if (value === undefined || value === null || value === '') return undefined
  if (value === 'true') return true
  if (value === 'false') return false
  if (!Number.isNaN(Number(value)) && String(Number(value)) === String(value)) return Number(value)
  return value
}

function parseTaskArgCondition(condition) {
  const operator = resolveTaskArgConditionOperator(condition)
  if (!operator) return { k: condition.k }
  if (operator !== 'in') return { k: condition.k, [operator]: parseConditionScalar(condition[operator]) }
  if (Array.isArray(condition.in)) return { k: condition.k, in: condition.in }
  try {
    const values = JSON.parse(condition.in)
    return { k: condition.k, in: Array.isArray(values) ? values : condition.in }
  } catch {
    return { k: condition.k, in: condition.in }
  }
}

function buildVariablePayload(variable) {
  const key = variable._key
  if (!key) return null
  const field = {
    t: variable.t,
    tp: variable.tp,
    req: Boolean(variable.req),
    note: variable.note || '',
  }
  if (variable.tp === 'str' && variable.ui === 'path') field.ui = 'path'
  if (variable.def !== '' && variable.def !== null && variable.def !== undefined) field.def = variable.def
  if (variable.tp === 'int' || variable.tp === 'num') {
    if (variable.min !== undefined && variable.min !== null) field.min = variable.min
    if (variable.max !== undefined && variable.max !== null) field.max = variable.max
  } else if (variable.tp === 'enum') {
    const options = cleanEnumOptions(variable.oneOf)
    if (options.length) field.oneOf = options
  }
  return { key, field }
}

export function buildTemplatePayload(localData, varsList, { clone = false } = {}) {
  const result = {
    v: localData.v,
    id: localData.id,
    t: localData.t,
    d: localData.d,
    vars: {},
    tasks: (localData.tasks || []).map(task => ({
      k: task.k,
      t: task.t,
      fn: task.fn,
      args: Array.isArray(task.args) ? task.args.map((arg) => {
        const key = taskArgKey(arg)
        const condition = taskArgCondition(arg)
        return condition ? { k: key, if: parseTaskArgCondition(condition) } : key
      }).filter(taskArgKey) : [],
    })),
    flows: (localData.flows || []).map(flow => ({
      k: flow.k,
      t: flow.t,
      g: Array.isArray(flow.g) ? flow.g.filter(Boolean) : [],
      steps: (flow.steps || []).map(step => ({
        k: step.k,
        task: step.task,
        args: step.args && typeof step.args === 'object' ? step.args : {},
        onSuccess: step.onSuccess || 'continue',
        ...(step.onSuccess === 'goto' && step.successGoto ? { successGoto: step.successGoto } : {}),
        onFail: step.onFail || 'stop',
        ...(step.onFail === 'goto' && step.goto ? { goto: step.goto } : {}),
      })),
    })),
  }

  for (const variable of varsList || []) {
    const payload = buildVariablePayload(variable)
    if (!payload) continue
    result.vars[payload.key] = payload.field
  }
  return clone ? JSON.parse(JSON.stringify(result)) : result
}
