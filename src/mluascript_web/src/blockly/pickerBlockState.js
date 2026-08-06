function formatFunctionSelection(values) {
  if (!values.length) return '未选择函数'
  if (values.length <= 2) return values.join('，')
  return `${values[0]} 等 ${values.length} 个`
}

export function restoreSerializedPickerLabel(block) {
  if (!block?.getFieldValue || !block?.setFieldValue) return
  if (block.type === 'lua_require_module_stmt' || block.type === 'lua_require_module_expr') {
    block.setFieldValue(block.getFieldValue('MODULE_VALUE') || '未选择', 'MODULE_LABEL')
    return
  }
  if (block.type === 'lua_dofile_stmt') {
    block.setFieldValue(block.getFieldValue('FILE_VALUE') || '未选择', 'FILE_LABEL')
    return
  }
  if (block.type === 'lua_module_export_function') {
    let values = []
    try {
      const parsed = JSON.parse(block.getFieldValue('FUNC_VALUES') || '[]')
      if (Array.isArray(parsed)) values = parsed.map(item => String(item || '')).filter(Boolean)
    } catch {}
    block.setFieldValue(formatFunctionSelection(values), 'FUNC_LABEL')
  }
}
