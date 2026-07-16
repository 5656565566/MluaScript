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

export function createTemplateVariable(parentKey = '', eqValue = undefined) {
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
    _showAdvanced: Boolean(parentKey),
  }
}

export function createTemplateTask() {
  return { k: '', t: '', fn: '', args: [], _fnArgs: ['args'] }
}

export function createTemplateFlow() {
  return { k: '', t: '', g: [], steps: [] }
}

export function createTemplateFlowStep() {
  return { k: '', task: '', args: {}, onFail: 'stop' }
}

export function createEnumOption() {
  return { v: '', t: '', children: [] }
}

function defaultValueForType(type) {
  if (type === 'bool') return false
  if (type === 'int') return null
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
  return {
    _key: key !== undefined ? key : (value.k || ''),
    t: value.t || '',
    tp: value.tp || 'str',
    def: value.def !== undefined ? value.def : defaultValueForType(value.tp || 'str'),
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
    args: Array.isArray(task.args) ? task.args.filter(Boolean) : [],
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
  return {
    localData: {
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
          onFail: step.onFail || 'stop',
        })) : [],
      })) : [],
    },
    varsList: flattenParsedVars(data.vars || {}),
  }
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

  for (const variable of varsList || []) {
    if (variable?.if?.k === oldKey) variable.if.k = newKey
  }
  for (const task of localData?.tasks || []) {
    task.args = mapUniqueValues(task.args, oldKey, newKey)
  }
  for (const flow of localData?.flows || []) {
    flow.g = mapUniqueValues(flow.g, oldKey, newKey)
    for (const step of flow.steps || []) {
      if (!step?.args || typeof step.args !== 'object') continue
      const nextArgs = {}
      for (const [key, value] of Object.entries(step.args)) {
        const mappedKey = key === oldKey ? newKey : key
        if (!mappedKey || Object.prototype.hasOwnProperty.call(nextArgs, mappedKey)) continue
        nextArgs[mappedKey] = value === oldKey ? newKey : value
      }
      step.args = nextArgs
    }
  }
}

function cleanEnumOptions(options) {
  return (options || [])
    .map(option => ({ v: option?.v ?? '', t: option?.t ?? '' }))
    .filter(option => option.v !== '')
}

function parseIfEqValue(value) {
  if (value === undefined || value === null || value === '') return undefined
  if (value === 'true') return true
  if (value === 'false') return false
  if (!Number.isNaN(Number(value)) && String(Number(value)) === String(value)) return Number(value)
  return value
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
  if (variable.def !== '' && variable.def !== null && variable.def !== undefined) field.def = variable.def
  if (variable.tp === 'int') {
    if (variable.min !== undefined && variable.min !== null) field.min = variable.min
    if (variable.max !== undefined && variable.max !== null) field.max = variable.max
  } else if (variable.tp === 'enum') {
    const options = cleanEnumOptions(variable.oneOf)
    if (options.length) field.oneOf = options
  }
  if (variable.if?.k) {
    field.if = { k: variable.if.k }
    const eqValue = parseIfEqValue(variable.if.eq)
    if (eqValue !== undefined) field.if.eq = eqValue
  }
  return { key, field }
}

function attachEnumChildren(parentKey, parentPayload, payloadMap) {
  if (!Array.isArray(parentPayload?.oneOf)) return
  for (const option of parentPayload.oneOf) {
    const children = [...payloadMap.values()].filter(payload => (
      !payload.mounted
      && payload.field.if?.k === parentKey
      && String(payload.field.if?.eq ?? '') === String(option?.v ?? '')
    ))
    if (!children.length) continue
    option.children = children.map(payload => ({ k: payload.key, ...payload.field }))
    children.forEach((payload, index) => {
      payload.mounted = true
      delete payload.field.if
      delete option.children[index].if
    })
  }
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
      args: Array.isArray(task.args) ? task.args.filter(Boolean) : [],
    })),
    flows: (localData.flows || []).map(flow => ({
      k: flow.k,
      t: flow.t,
      g: Array.isArray(flow.g) ? flow.g.filter(Boolean) : [],
      steps: (flow.steps || []).map(step => ({
        k: step.k,
        task: step.task,
        args: step.args && typeof step.args === 'object' ? step.args : {},
        onFail: step.onFail || 'stop',
      })),
    })),
  }

  const payloadMap = new Map()
  for (const variable of varsList || []) {
    const payload = buildVariablePayload(variable)
    if (!payload) continue
    payloadMap.set(payload.key, payload)
    result.vars[payload.key] = payload.field
  }

  for (const payload of payloadMap.values()) {
    const conditionKey = payload.field.if?.k
    if (!conditionKey) continue
    const parent = payloadMap.get(conditionKey)?.field
    if (!parent || parent.tp === 'enum') continue
    parent.children = parent.children || []
    parent.children.push({ k: payload.key, ...payload.field })
    payload.mounted = true
    delete payload.field.if
  }
  // Rebuild enum-dependent children after ordinary conditional children are mounted.
  for (const [key, payload] of payloadMap.entries()) {
    attachEnumChildren(key, payload.field, payloadMap)
  }
  for (const payload of payloadMap.values()) {
    if (payload.mounted) delete result.vars[payload.key]
  }
  return clone ? JSON.parse(JSON.stringify(result)) : result
}
