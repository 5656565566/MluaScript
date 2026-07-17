function getWorkspaceVariableMap(workspace) {
  return workspace?.getVariableMap?.() || null
}

export function getWorkspaceVariablesOfType(workspace, type = '') {
  return getWorkspaceVariableMap(workspace)?.getVariablesOfType(type) || []
}

export function getWorkspaceAllVariables(workspace) {
  return getWorkspaceVariableMap(workspace)?.getAllVariables() || []
}

export function getWorkspaceVariableById(workspace, variableId) {
  if (!variableId) return null
  return getWorkspaceVariableMap(workspace)?.getVariableById(variableId) || null
}

export function deleteWorkspaceVariableById(workspace, variableId) {
  const variableMap = getWorkspaceVariableMap(workspace)
  const variable = variableMap?.getVariableById(variableId) || null
  if (!variable) return false

  // Blockly 13 将变量的直接删除入口收敛到了 VariableMap
  variableMap.deleteVariable(variable)
  return true
}
