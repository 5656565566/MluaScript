export function resolveProcedureArgumentLuaName(procedureBlock, selectedName, generator) {
  const normalizedName = String(selectedName || '').trim()
  if (!procedureBlock || !normalizedName || typeof generator?.getVariableName !== 'function') return ''

  const models = typeof procedureBlock.getVarModels === 'function'
    ? procedureBlock.getVarModels()
    : procedureBlock.argumentVarModels_
  const argumentModels = Array.isArray(models) ? models : []
  const model = argumentModels.find(item => String(item?.getName?.() || '').trim() === normalizedName)
  const variableId = model?.getId?.()
  return variableId ? generator.getVariableName(variableId) : ''
}
