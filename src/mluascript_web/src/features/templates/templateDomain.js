export function cloneValue(value) {
  if (Array.isArray(value)) return value.map(item => cloneValue(item))
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

function taskArgKey(arg) {
  return typeof arg === 'string' ? arg : String(arg?.k || '')
}

function taskArgCondition(arg) {
  return typeof arg === 'string' || !arg?.if?.k ? null : arg.if
}

export function fieldDefaultValue(field) {
  if (Object.prototype.hasOwnProperty.call(field || {}, 'default')) return cloneValue(field.default)
  if (Object.prototype.hasOwnProperty.call(field || {}, 'def')) return cloneValue(field.def)
  if (fieldType(field) === 'bool') return false
  return ''
}

export function normalizeRuntimeValue(field, value) {
  const type = fieldType(field)
  if (type === 'int' || type === 'num') {
    if (value === '' || value === null || typeof value === 'undefined') return ''
    const num = Number(value)
    if (Number.isNaN(num)) return ''
    return type === 'int' ? Math.trunc(num) : num
  }
  if (type === 'bool') return Boolean(value)
  if (type === 'json') {
    if (typeof value !== 'string') return cloneValue(value)
    const text = value.trim()
    if (!text) return null
    try {
      return JSON.parse(text)
    } catch {
      return value
    }
  }
  return value
}

export function isTemplateConditionActive(condition, currentValue) {
  if (!condition?.k) return true
  if (Array.isArray(condition.in) && condition.in.length) return condition.in.includes(currentValue)
  const numericOperator = ['gt', 'gte', 'lt', 'lte']
    .find(operator => Object.prototype.hasOwnProperty.call(condition, operator))
  if (numericOperator) {
    const targetValue = condition[numericOperator]
    if (!Number.isFinite(currentValue) || !Number.isFinite(targetValue)) return false
    if (numericOperator === 'gt') return currentValue > targetValue
    if (numericOperator === 'gte') return currentValue >= targetValue
    if (numericOperator === 'lt') return currentValue < targetValue
    return currentValue <= targetValue
  }
  if (Object.prototype.hasOwnProperty.call(condition, 'ne')) return currentValue !== condition.ne
  if (Object.prototype.hasOwnProperty.call(condition, 'eq')) return currentValue === condition.eq
  return Boolean(currentValue)
}

export function resolveTemplateBinding(value, vars, runtimeValues = {}) {
  if (!value || typeof value !== 'object' || !value.$bind) return cloneValue(value)
  if (value.$bind === 'literal') return cloneValue(value.value)
  if (value.$bind !== 'var') return cloneValue(value)

  const key = String(value.key || '')
  if (Object.prototype.hasOwnProperty.call(runtimeValues, key)) return cloneValue(runtimeValues[key])
  return fieldDefaultValue(vars?.[key])
}

export function normalizeTemplateField(field, key = '') {
  const normalizedKey = key || fieldKey(field)
  const type = fieldType(field)
  const rawCondition = field?.if || null
  const normalizedCondition = rawCondition
    ? { ...rawCondition, in: Array.isArray(rawCondition.in) ? rawCondition.in : [] }
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
    ui: field?.ui || '',
    if: normalizedCondition,
    grp: field?.grp || '',
    as: field?.as || '',
  }
}

export function normalizeTemplateMeta(meta) {
  if (!meta) return null
  const vars = meta.vars || {}
  const normalizedVars = Object.fromEntries(Object.entries(vars).map(([key, field]) => [key, normalizeTemplateField(field, key)]))
  const rawTasks = Array.isArray(meta.tasks) ? meta.tasks : Array.isArray(meta.taskCatalog) ? meta.taskCatalog : []
  const tasks = rawTasks.map(task => ({
    ...task,
    args: Array.isArray(task.args) ? task.args.map(arg => typeof arg === 'string' ? arg : ({ ...arg, if: arg.if ? { ...arg.if } : null })) : [],
  }))
  const taskMap = Object.fromEntries(tasks.map(task => [task.k || task.key, task]))
  const workflows = (Array.isArray(meta.flows) ? meta.flows : Array.isArray(meta.workflows) ? meta.workflows : []).map((flow) => {
    const workflowKey = flow.k || flow.key || ''
    const globals = (flow.g || flow.globals || []).map(key => normalizedVars[key]).filter(Boolean)
    const steps = (flow.steps || flow.tasks || []).map((step) => {
      const taskRef = step.task || step.taskRef || ''
      const taskDef = taskMap[taskRef] || {}
      const argRefs = Array.isArray(taskDef.args) ? taskDef.args : []
      const argKeys = argRefs.map(taskArgKey).filter(Boolean)
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
        onSuccess: step.onSuccess || 'continue',
        successGoto: step.successGoto || '',
        onFail: step.onFail || 'stop',
        allowDisable: step.allowDisable !== false,
        allowReorder: step.allowReorder !== false,
        fields: argRefs.map((arg) => {
          const key = taskArgKey(arg)
          const field = normalizedVars[key]
          if (!field) return null
          const condition = taskArgCondition(arg)
          return {
            ...field,
            if: condition ? { ...condition, in: Array.isArray(condition.in) ? condition.in : [] } : null,
            grp: condition?.k || '',
          }
        }).filter(Boolean),
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

export function normalizeTemplateSavedConfig(savedConfig) {
  if (!savedConfig || typeof savedConfig !== 'object') return {}
  return {
    ...savedConfig,
    flows: savedConfig.flows || savedConfig.workflows || {},
    tasks: savedConfig.tasks || {},
  }
}

export function buildTaskDefaults(meta, savedConfig) {
  const next = {}
  for (const task of meta?.tasks || []) {
    const taskKey = task.k || task.key
    next[taskKey] = { ...(savedConfig?.tasks?.[taskKey]?.params || {}) }
  }
  return next
}

export function buildWorkflowDefaults(meta, savedConfig) {
  const next = {}
  for (const workflow of meta?.workflows || []) {
    const workflowKey = workflow.key
    const savedWorkflow = savedConfig?.flows?.[workflowKey] || savedConfig?.workflows?.[workflowKey] || {}
    const savedStepArgs = savedWorkflow.stepArgs || {}
    const savedStepEnabled = savedWorkflow.stepEnabled || {}
    const savedStepOrder = Array.isArray(savedWorkflow.stepOrder) ? savedWorkflow.stepOrder : []
    const savedGlobals = savedWorkflow.globals || {}
    const runtimeGlobals = Object.fromEntries(Object.entries(meta?.vars || {}).map(([key, field]) => [
      key,
      Object.prototype.hasOwnProperty.call(savedGlobals, key) ? cloneValue(savedGlobals[key]) : fieldDefaultValue(field),
    ]))
    const tasks = workflow.tasks || []
    next[workflowKey] = {
      stepOrder: savedStepOrder.length
        ? savedStepOrder.filter(key => tasks.some(step => step.key === key)).concat(tasks.map(step => step.key).filter(key => !savedStepOrder.includes(key)))
        : tasks.map(step => step.key),
      stepEnabled: Object.fromEntries(tasks.map(step => [step.key, Object.prototype.hasOwnProperty.call(savedStepEnabled, step.key) ? Boolean(savedStepEnabled[step.key]) : Boolean(step.enabled ?? true)])),
      stepArgs: Object.fromEntries(tasks.map(step => {
        const defaults = Object.fromEntries((step.fields || []).map(field => [field.key, fieldDefaultValue(field)]))
        const boundDefaults = Object.fromEntries(Object.entries(step.args || {}).map(([key, value]) => [
          key,
          resolveTemplateBinding(value, meta?.vars, runtimeGlobals),
        ]))
        return [step.key, { ...defaults, ...boundDefaults, ...(savedStepArgs[step.key] || {}) }]
      })),
      globals: Object.fromEntries((workflow.globals || []).map(field => [field.key, Object.prototype.hasOwnProperty.call(savedGlobals, field.key) ? cloneValue(savedGlobals[field.key]) : fieldDefaultValue(field)])),
    }
  }
  return next
}

