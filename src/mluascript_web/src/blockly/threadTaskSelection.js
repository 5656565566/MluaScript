import * as Blockly from 'blockly'
import { luaOrder } from './constants.js'
import { getBlockSemanticDiagnostic } from './blockSemanticDiagnostics.js'
import { getSelectableProjectModules } from '../features/projects/projectModuleRegistry.js'

export function getThreadTaskSelection(block) {
  let params = []
  try {
    const parsed = JSON.parse(block.getFieldValue('PARAM_VALUES') || '[]')
    if (Array.isArray(parsed)) params = parsed.map(item => String(item || ''))
  } catch {}
  return {
    kind: block.getFieldValue('TARGET_KIND') || '',
    moduleKey: block.getFieldValue('MODULE_VALUE') || '',
    functionName: block.getFieldValue('FUNCTION_VALUE') || '',
    params,
    callStyle: block.getFieldValue('CALL_STYLE') === 'method' ? 'method' : 'function',
  }
}

function updateThreadTaskArguments(block, params) {
  const current = (block.inputList || []).filter(input => input.name?.startsWith('ARG_'))
  if (JSON.stringify(block.threadTaskParams_ || []) === JSON.stringify(params)
    && current.length === params.length
    && current.every((input, index) => input.name === `ARG_${index}`)) return
  const targets = current.map(input => input.connection?.targetConnection || null)
  for (const target of targets) target?.disconnect?.()
  for (const input of current) block.removeInput(input.name, true)
  params.forEach((name, index) => {
    block.appendValueInput(`ARG_${index}`).appendField(name || `参数 ${index + 1}`)
    const connection = block.getInput(`ARG_${index}`)?.connection
    if (connection && targets[index]) connection.connect(targets[index])
  })
  block.threadTaskParams_ = [...params]
}

export function restoreThreadTaskSelection(block, state = getThreadTaskSelection(block)) {
  const kind = state.kind === 'local' || state.kind === 'module' ? state.kind : ''
  const moduleKey = kind === 'module' ? String(state.moduleKey || '') : ''
  const functionName = String(state.functionName || '')
  const params = Array.isArray(state.params) ? state.params.map(item => String(item || '')) : []
  const callStyle = state.callStyle === 'method' ? 'method' : 'function'
  block.setFieldValue(kind, 'TARGET_KIND')
  block.setFieldValue(moduleKey, 'MODULE_VALUE')
  block.setFieldValue(functionName, 'FUNCTION_VALUE')
  block.setFieldValue(JSON.stringify(params), 'PARAM_VALUES')
  block.setFieldValue(callStyle, 'CALL_STYLE')
  block.setFieldValue(functionName ? (moduleKey ? `${moduleKey} · ${functionName}` : functionName) : '未选择函数', 'TARGET_LABEL')
  updateThreadTaskArguments(block, params)
}

export function installThreadTaskSerialization(block) {
  block.mutationToDom = () => {
    const state = getThreadTaskSelection(block)
    const mutation = Blockly.utils.xml.createElement('mutation')
    mutation.setAttribute('kind', state.kind)
    mutation.setAttribute('module', state.moduleKey)
    mutation.setAttribute('function', state.functionName)
    mutation.setAttribute('params', JSON.stringify(state.params))
    mutation.setAttribute('call_style', state.callStyle)
    return mutation
  }
  block.domToMutation = mutation => {
    let params = []
    try {
      const parsed = JSON.parse(mutation.getAttribute('params') || '[]')
      if (Array.isArray(parsed)) params = parsed
    } catch {}
    restoreThreadTaskSelection(block, {
      kind: mutation.getAttribute('kind') || '',
      moduleKey: mutation.getAttribute('module') || '',
      functionName: mutation.getAttribute('function') || '',
      params,
      callStyle: mutation.getAttribute('call_style') || 'function',
    })
  }
  block.saveExtraState = () => getThreadTaskSelection(block)
  block.loadExtraState = state => restoreThreadTaskSelection(block, state)
}

export function getThreadTaskPickerItems(workspace, currentSource = '') {
  const local = (workspace?.getTopBlocks?.(false) || [])
    .filter(block => block?.type === 'procedures_defnoreturn' || block?.type === 'procedures_defreturn')
    .map(block => ({
      name: block.getFieldValue('NAME') || '',
      params: block.getProcedureDef?.()?.[1] || [],
    }))
    .filter(item => item.name)
    .map(item => ({
      value: JSON.stringify(['local', item.name]),
      label: item.name,
      group: '当前文件',
      kind: 'local',
      functionName: item.name,
      params: item.params,
    }))
  const modules = getSelectableProjectModules(currentSource).flatMap(module => module.exports.map(item => ({
    value: JSON.stringify(['module', module.key, item.name]),
    label: `${module.key} · ${item.name}`,
    group: module.kind === 'blockly' ? 'Blockly 模块' : 'Lua 模块',
    kind: 'module',
    moduleKey: module.key,
    functionName: item.name,
    params: Array.isArray(item.params) ? item.params : [],
    callStyle: item.callStyle,
  })))
  return [...local, ...modules]
}

export function createThreadTaskPickerConfig(block, currentSource = '', updatePicker) {
  const items = getThreadTaskPickerItems(block.workspace, currentSource)
  const state = getThreadTaskSelection(block)
  const localItems = items.filter(item => item.kind === 'local')
  const modules = getSelectableProjectModules(currentSource)
  const openRootStep = () => {
    updatePicker(rootConfig)
    return false
  }
  const openLocalStep = () => {
    updatePicker({
      title: '选择当前文件函数',
      items: localItems,
      currentValue: state.kind === 'local' ? JSON.stringify(['local', state.functionName]) : null,
      emptyText: '当前文件没有定义函数',
      manageButtonText: '返回',
      onManage: openRootStep,
      onSelect: value => {
        const selected = localItems.find(item => item.value === value)
        if (selected) restoreThreadTaskSelection(block, selected)
      },
    })
    return false
  }
  const openFunctionStep = moduleKey => {
    const module = modules.find(item => item.key === moduleKey)
    const functionItems = items
      .filter(item => item.kind === 'module' && item.moduleKey === moduleKey)
      .map(item => ({
        ...item,
        label: item.functionName,
        description: `${item.functionName}(${item.params.join(', ')})`,
      }))
    updatePicker({
      title: `选择 ${moduleKey} 的导出函数`,
      subtitle: module?.source || moduleKey,
      items: functionItems,
      currentValue: state.kind === 'module' && state.moduleKey === moduleKey
        ? JSON.stringify(['module', moduleKey, state.functionName]) : null,
      emptyText: '该模块没有可静态识别的导出函数',
      manageButtonText: '返回模块',
      onManage: openModuleStep,
      onSelect: value => {
        const selected = functionItems.find(item => item.value === value)
        if (selected) restoreThreadTaskSelection(block, selected)
      },
    })
    return false
  }
  const openModuleStep = () => {
    updatePicker({
      title: '选择项目模块',
      subtitle: '先选择模块，再选择它显式导出的函数',
      items: modules.map(module => ({
        value: module.key,
        label: module.key,
        description: `${module.source} · ${module.exports.length} 个静态导出`,
        group: module.kind === 'blockly' ? 'Blockly' : 'Lua',
      })),
      currentValue: state.kind === 'module' ? state.moduleKey : null,
      emptyText: '当前项目没有其他已导出函数的模块',
      manageButtonText: '返回',
      onManage: openRootStep,
      onSelect: openFunctionStep,
    })
    return false
  }
  const rootConfig = {
    title: '选择后台任务函数',
    subtitle: '先选择来源，再选择一个函数',
    items: [
      { value: 'local', label: '当前文件', description: `${localItems.length} 个函数` },
      { value: 'module', label: '项目模块', description: `${modules.length} 个有导出函数的模块` },
    ],
    currentValue: state.kind || null,
    onManage: null,
    onSelect: value => value === 'local' ? openLocalStep() : value === 'module' ? openModuleStep() : false,
  }
  return rootConfig
}

export function generateThreadTask(block, generator) {
  const diagnostic = getBlockSemanticDiagnostic(block)
  if (diagnostic) throw new Error(diagnostic)
  const state = getThreadTaskSelection(block)
  const args = state.params.map((_, index) => generator.valueToCode(block, `ARG_${index}`, luaOrder) || 'nil')
  if (state.kind === 'local') {
    const name = generator.nameDB_
      ? generator.nameDB_.getName(state.functionName, Blockly.PROCEDURE_CATEGORY_NAME || 'PROCEDURE')
      : state.functionName
    return [`thread.spawn(${JSON.stringify(name)}${args.length ? `, nil, ${args.join(', ')}` : ''})`, luaOrder]
  }
  const helperName = generator.provideFunction_('mlua_project_task', [
    `function ${generator.FUNCTION_NAME_PLACEHOLDER_}(moduleKey, functionName, callStyle, ...)`,
    '  local module = require(moduleKey)',
    '  local target = module[functionName]',
    '  if callStyle == "method" then return target(module, ...) end',
    '  return target(...)',
    'end',
  ])
  const values = [state.moduleKey, state.functionName, state.callStyle].map(JSON.stringify)
  return [`thread.spawn(${JSON.stringify(helperName)}, nil, ${[...values, ...args].join(', ')})`, luaOrder]
}

export function generateThreadTaskId(block, generator) {
  const handle = generator.valueToCode(block, 'HANDLE', luaOrder) || 'nil'
  return [`(${handle}):id()`, luaOrder]
}
