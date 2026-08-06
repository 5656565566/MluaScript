import { getProjectModuleRegistry } from '../features/projects/projectModuleRegistry.js'

function getDefinedProcedureNames(workspace) {
  if (!workspace || typeof workspace.getTopBlocks !== 'function') return new Set()
  return new Set(
    workspace
      .getTopBlocks(false)
      .filter(block => block?.type === 'procedures_defnoreturn' || block?.type === 'procedures_defreturn')
      .map(block => String(block.getFieldValue?.('NAME') || '').trim())
      .filter(Boolean),
  )
}

function getThreadSpawnDiagnostic(block) {
  const target = block.getInputTargetBlock?.('FUNC_CALL')
  if (!target) return '请嵌入一个函数调用块'
  const supported = target.type === 'procedures_callnoreturn'
    || target.type === 'procedures_callreturn'
    || target.type === 'procedure_call_picker'
  if (!supported) return '这里只能嵌入函数调用块'
  if (target.getNextBlock?.()) return '后台任务只能包含一个函数调用块'
  return ''
}

function getModuleExportDiagnostic(block, workspace) {
  const exportBlocks = workspace?.getTopBlocks?.(false)
    ?.filter(item => item?.type === 'lua_module_export_function') || []
  if (exportBlocks.length > 1) return '模块导出根块只能存在一个'

  let selectedNames
  try {
    selectedNames = JSON.parse(block.getFieldValue?.('FUNC_VALUES') || '[]')
  } catch {
    return '模块导出函数列表格式无效'
  }
  if (!Array.isArray(selectedNames)) return '模块导出函数列表格式无效'
  selectedNames = selectedNames.map(name => String(name || '').trim()).filter(Boolean)
  if (!selectedNames.length) return '请选择要导出的函数'

  const definedNames = getDefinedProcedureNames(workspace)
  const missingNames = selectedNames.filter(name => !definedNames.has(name))
  return missingNames.length ? `导出函数不存在：${missingNames.join('、')}` : ''
}

function getTemplateDiagnostic(block, workspace) {
  let data
  try {
    data = JSON.parse(block.getFieldValue?.('TEMPLATE_JSON') || '{}')
  } catch {
    return '模板配置数据格式无效'
  }
  const definedNames = getDefinedProcedureNames(workspace)
  const tasks = Array.isArray(data?.tasks) ? data.tasks : []
  for (const task of tasks) {
    const taskName = String(task?.k || task?.t || '未命名任务').trim()
    const functionName = String(task?.fn || '').trim()
    if (!functionName) return `任务 ${taskName} 未选择 Blockly 函数`
    if (!definedNames.has(functionName)) return `任务 ${taskName} 引用的 Blockly 函数不存在：${functionName}`
  }
  return ''
}

export function getBlockSemanticDiagnostic(block, workspace = block?.workspace) {
  if (!block || block.isDisposed?.()) return ''
  if (block.type === 'thread_spawn_function') return getThreadSpawnDiagnostic(block)
  if (block.type === 'lua_require_module_stmt' || block.type === 'lua_require_module_expr') {
    return block.getFieldValue?.('MODULE_VALUE') ? '' : '请选择要导入的模块'
  }
  if (block.type === 'lua_project_module_call_stmt' || block.type === 'lua_project_module_call_expr') {
    const moduleKey = block.getFieldValue?.('MODULE_VALUE') || ''
    const functionName = block.getFieldValue?.('FUNCTION_VALUE') || ''
    if (!moduleKey || !functionName) return '请选择项目模块导出函数'
    const module = getProjectModuleRegistry().find(item => item.key === moduleKey)
    if (!module) return `项目模块不存在：${moduleKey}`
    const exported = (module.exports || []).find(item => item.name === functionName)
    if (!exported) return `模块 ${moduleKey} 不再导出函数：${functionName}`
    let savedParams = []
    try { savedParams = JSON.parse(block.getFieldValue?.('PARAM_VALUES') || '[]') } catch {}
    const currentParams = Array.isArray(exported.params) ? exported.params : []
    if (JSON.stringify(savedParams) !== JSON.stringify(currentParams)) {
      return `函数参数已变化，请重新选择：${moduleKey}.${functionName}`
    }
    const savedCallStyle = block.getFieldValue?.('CALL_STYLE') || 'function'
    const currentCallStyle = exported.callStyle === 'method' ? 'method' : 'function'
    if (savedCallStyle !== currentCallStyle) {
      return `函数调用方式已变化，请重新选择：${moduleKey}.${functionName}`
    }
    if (block.type === 'lua_project_module_call_expr' && exported.hasReturn === false) {
      return `函数没有返回值：${moduleKey}.${functionName}`
    }
    return ''
  }
  if (block.type === 'lua_dofile_stmt') {
    return block.getFieldValue?.('FILE_VALUE') ? '' : '请选择要执行的 Lua 文件'
  }
  if (block.type === 'lua_module_export_function') return getModuleExportDiagnostic(block, workspace)
  if (block.type === 'maa_template_config') return getTemplateDiagnostic(block, workspace)
  return ''
}

export function attachBlockSemanticWarning(block, beforeRefresh = null) {
  const refresh = () => {
    if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
    if (typeof beforeRefresh === 'function') beforeRefresh()
    block.setWarningText(getBlockSemanticDiagnostic(block))
  }
  block.setOnChange(refresh)
  refresh()
}
