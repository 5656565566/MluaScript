import * as Blockly from 'blockly'
import { replaceCallableBlock } from './blockReplacement.js'

export function updateProjectModuleCallShape(block, params = []) {
  const normalizedParams = params.map(item => String(item || ''))
  const currentArgumentInputs = (block.inputList || []).filter(input => input.name?.startsWith('ARG_'))
  if (JSON.stringify(block.projectModuleParams_ || []) === JSON.stringify(normalizedParams)
    && currentArgumentInputs.length === normalizedParams.length
    && currentArgumentInputs.every((input, index) => input.name === `ARG_${index}`)) {
    return
  }
  const childTargets = currentArgumentInputs.map(input => input.connection?.targetConnection || null)
  for (const target of childTargets) target?.disconnect?.()
  for (const input of [...(block.inputList || [])]) {
    if (input.name?.startsWith('ARG_')) block.removeInput(input.name, true)
  }
  normalizedParams.forEach((name, index) => {
    block.appendValueInput(`ARG_${index}`).appendField(name || `参数 ${index + 1}`)
    const inputConnection = block.getInput?.(`ARG_${index}`)?.connection
    if (inputConnection && childTargets[index]) inputConnection.connect(childTargets[index])
  })
  block.projectModuleParams_ = normalizedParams
}

export function getProjectModuleCallState(block) {
  let params = []
  try {
    const parsed = JSON.parse(block?.getFieldValue?.('PARAM_VALUES') || '[]')
    if (Array.isArray(parsed)) params = parsed.map(item => String(item || ''))
  } catch {}
  return {
    moduleKey: String(block?.getFieldValue?.('MODULE_VALUE') || ''),
    functionName: String(block?.getFieldValue?.('FUNCTION_VALUE') || ''),
    params,
    callStyle: block?.getFieldValue?.('CALL_STYLE') === 'method' ? 'method' : 'function',
  }
}

export function restoreProjectModuleCallState(block, state = getProjectModuleCallState(block)) {
  const moduleKey = String(state?.moduleKey || '')
  const functionName = String(state?.functionName || '')
  const params = Array.isArray(state?.params) ? state.params.map(item => String(item || '')) : []
  const callStyle = state?.callStyle === 'method' ? 'method' : 'function'
  block.setFieldValue(moduleKey, 'MODULE_VALUE')
  block.setFieldValue(functionName, 'FUNCTION_VALUE')
  block.setFieldValue(JSON.stringify(params), 'PARAM_VALUES')
  block.setFieldValue(callStyle, 'CALL_STYLE')
  block.setFieldValue(moduleKey && functionName ? `${moduleKey} · ${functionName}` : '未选择', 'CALL_LABEL')
  updateProjectModuleCallShape(block, params)
}

export function installProjectModuleCallSerialization(block) {
  block.mutationToDom = () => {
    const state = getProjectModuleCallState(block)
    const mutation = Blockly.utils.xml.createElement('mutation')
    mutation.setAttribute('module', state.moduleKey)
    mutation.setAttribute('function', state.functionName)
    mutation.setAttribute('params', JSON.stringify(state.params))
    mutation.setAttribute('call_style', state.callStyle)
    return mutation
  }
  block.domToMutation = (mutation) => {
    let params = []
    try {
      const parsed = JSON.parse(mutation.getAttribute('params') || '[]')
      if (Array.isArray(parsed)) params = parsed
    } catch {}
    restoreProjectModuleCallState(block, {
      moduleKey: mutation.getAttribute('module') || '',
      functionName: mutation.getAttribute('function') || '',
      params,
      callStyle: mutation.getAttribute('call_style') || 'function',
    })
  }
  block.saveExtraState = () => getProjectModuleCallState(block)
  block.loadExtraState = (state) => restoreProjectModuleCallState(block, state)
}

export function migrateLegacyProjectModuleCallXml(root) {
  if (!root?.getElementsByTagName) return
  for (const blockElement of root.getElementsByTagName('block')) {
    const type = blockElement.getAttribute('type') || ''
    if (type !== 'lua_project_module_call_stmt' && type !== 'lua_project_module_call_expr') continue
    const directChildren = [...blockElement.children]
    if (directChildren.some(child => child.nodeName.toLowerCase() === 'mutation')) continue
    const fields = new Map(
      directChildren
        .filter(child => child.nodeName.toLowerCase() === 'field')
        .map(child => [child.getAttribute('name') || '', child.textContent || '']),
    )
    let params = []
    try {
      const parsed = JSON.parse(fields.get('PARAM_VALUES') || '[]')
      if (Array.isArray(parsed)) params = parsed
    } catch {}
    const mutation = Blockly.utils.xml.createElement('mutation')
    mutation.setAttribute('module', fields.get('MODULE_VALUE') || '')
    mutation.setAttribute('function', fields.get('FUNCTION_VALUE') || '')
    mutation.setAttribute('params', JSON.stringify(params))
    mutation.setAttribute('call_style', fields.get('CALL_STYLE') === 'method' ? 'method' : 'function')
    blockElement.insertBefore(mutation, blockElement.firstChild)
  }
}

export function getProjectModuleCallBlockType(currentType, hasReturn) {
  if (hasReturn === true) return 'lua_project_module_call_expr'
  if (hasReturn === false) return 'lua_project_module_call_stmt'
  return currentType
}

export function applyProjectModuleFunctionSelection(block, moduleKey, item) {
  if (!block || !moduleKey || !item?.name) return null
  const targetType = getProjectModuleCallBlockType(block.type, item.hasReturn)
  return replaceCallableBlock(block, targetType, (targetBlock) => {
    restoreProjectModuleCallState(targetBlock, {
      moduleKey,
      functionName: item.name,
      params: item.params || [],
      callStyle: item.callStyle,
    })
  })
}
