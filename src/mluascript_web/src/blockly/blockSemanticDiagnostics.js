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
  if (block.type === 'lua_dofile_stmt') {
    return block.getFieldValue?.('FILE_VALUE') ? '' : '请选择要执行的 Lua 文件'
  }
  if (block.type === 'lua_module_export_function') return getModuleExportDiagnostic(block, workspace)
  if (block.type === 'maa_template_config') return getTemplateDiagnostic(block, workspace)
  return ''
}

export function attachBlockSemanticWarning(block) {
  const refresh = () => {
    if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
    block.setWarningText(getBlockSemanticDiagnostic(block))
  }
  block.setOnChange(refresh)
  refresh()
}
