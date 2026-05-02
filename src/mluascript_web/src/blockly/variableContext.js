import * as Blockly from 'blockly'
import { actions } from '../store'
import { pickerActions } from '../store/pickerState'

const VARIABLE_PICK_VALUE = '__MAA_PICK_VARIABLE__'
const VARIABLE_RENAME_VALUE = '__MAA_RENAME_VARIABLE__'
const VARIABLE_DELETE_PREFIX = '__MAA_DELETE_VARIABLE__:'

function normalizeVariableName(value, fallback = '') {
  return String(value || '').trim() || fallback
}

function getBlockY(block) {
  if (!block || typeof block.getRelativeToSurfaceXY !== 'function') return 0
  return Number(block.getRelativeToSurfaceXY()?.y || 0)
}

function getEnclosingProcedureBlock(block) {
  if (!block?.workspace) return null
  let parent = block
  while (parent) {
    if (parent.type === 'procedures_defnoreturn' || parent.type === 'procedures_defreturn') {
      return parent
    }
    parent = parent.getSurroundParent?.() || null
  }
  return null
}

function getProcedureArgumentNames(block) {
  const procedureBlock = getEnclosingProcedureBlock(block)
  if (!procedureBlock) return []
  const procedureDef = typeof procedureBlock.getProcedureDef === 'function'
    ? procedureBlock.getProcedureDef()
    : null
  const args = Array.isArray(procedureDef?.[1])
    ? procedureDef[1]
    : Array.isArray(procedureBlock.arguments_)
      ? procedureBlock.arguments_
      : []
  return args.map((arg) => normalizeVariableName(arg)).filter(Boolean)
}

function getProcedureArgumentVariableIds(workspace) {
  if (!workspace) return new Set()
  const argumentIds = new Set()
  const procedureBlocks = workspace.getAllBlocks(false).filter((block) =>
    block?.type === 'procedures_defnoreturn' || block?.type === 'procedures_defreturn'
  )
  for (const block of procedureBlocks) {
    const argumentVarModels = Array.isArray(block.argumentVarModels_) ? block.argumentVarModels_ : []
    for (const model of argumentVarModels) {
      const id = model?.getId?.()
      if (id) argumentIds.add(id)
    }
  }
  return argumentIds
}

function getWorkspaceGlobalVariables(workspace) {
  if (!workspace) return []
  const argumentIds = getProcedureArgumentVariableIds(workspace)
  return workspace
    .getVariablesOfType('')
    .filter((variable) => !argumentIds.has(variable.getId()))
    .map((variable) => ({
      id: variable.getId(),
      name: normalizeVariableName(variable.name),
      kind: 'global',
      label: normalizeVariableName(variable.name),
      value: variable.getId(),
      variableId: variable.getId(),
      description: '',
      blockId: null,
      scopeKey: 'global',
      y: -1,
    }))
    .filter((item) => item.name)
}

function getScopeKey(block) {
  if (!block) return 'global'
  const procedureBlock = getEnclosingProcedureBlock(block)
  if (procedureBlock) return `procedure:${procedureBlock.id}`

  // 所有不在函数内部的积木，共享同一个工作区级别的局部作用域
  return 'workspace'
}

function getBranchPath(block) {
  const path = []
  let current = block
  while (current) {
    const parent = current.getParent?.() || null
    if (!parent) break
    
    let isInput = false
    if (parent.inputList) {
      for (const input of parent.inputList) {
        if (input.connection?.targetBlock?.() === current) {
          path.push(`${parent.id}:${input.name}`)
          isInput = true
          break
        }
      }
    }
    current = parent
  }
  return path.reverse()
}

function isReachableBefore(candidate, target) {
  if (!candidate || !target) return false
  if (candidate.id === target.id) return true

  const candidatePath = getBranchPath(candidate)
  const targetPath = getBranchPath(target)

  if (candidatePath.length > targetPath.length) return false
  for (let i = 0; i < candidatePath.length; i++) {
    if (candidatePath[i] !== targetPath[i]) return false
  }

  let targetAncestor = target
  while (targetAncestor) {
    const p = getBranchPath(targetAncestor)
    if (p.length === candidatePath.length) {
      break
    }
    targetAncestor = targetAncestor.getParent?.() || null
  }

  if (!targetAncestor) return false

  let cursor = targetAncestor
  while (cursor) {
    if (cursor.id === candidate.id) return true
    cursor = cursor.getPreviousBlock?.() || null
  }

  const candidateTop = typeof candidate.getRootBlock === 'function' ? candidate.getRootBlock() : candidate
  const targetTop = typeof targetAncestor.getRootBlock === 'function' ? targetAncestor.getRootBlock() : targetAncestor
  
  if (candidateTop.getParent?.() === targetTop.getParent?.()) {
    return getBlockY(candidate) <= getBlockY(targetAncestor)
  }

  return false
}

function getDeclaredLocalVariables(block) {
  const workspace = block?.workspace || Blockly.getMainWorkspace()
  if (!workspace || !block || typeof workspace.getAllBlocks !== 'function') return []
  const scopeKey = getScopeKey(block)
  return workspace
    .getAllBlocks(false)
    .filter((candidate) => candidate?.type === 'local_var_declare')
    .filter((candidate) => getScopeKey(candidate) === scopeKey)
    .filter((candidate) => isReachableBefore(candidate, block))
    .map((candidate) => ({
      name: normalizeVariableName(candidate.getFieldValue?.('VAR'), 'item'),
      kind: 'local',
      label: normalizeVariableName(candidate.getFieldValue?.('VAR'), 'item'),
      value: normalizeVariableName(candidate.getFieldValue?.('VAR'), 'item'),
      variableId: null,
      description: '局部变量',
      blockId: candidate.id,
      scopeKey,
      y: getBlockY(candidate),
    }))
    .filter((item) => item.name)
}

function dedupeVariables(items) {
  const priority = { local: 3, argument: 2, global: 1 }
  const map = new Map()
  for (const item of items) {
    const key = item.name
    const existing = map.get(key)
    if (!existing || (priority[item.kind] || 0) > (priority[existing.kind] || 0)) {
      map.set(key, item)
    }
  }
  return [...map.values()]
}

export function getAvailableVariablesForBlock(block, options = {}) {
  const workspace = block?.workspace || Blockly.getMainWorkspace()
  const includeGlobals = options.includeGlobals !== false
  const includeLocals = options.includeLocals !== false
  const includeArguments = options.includeArguments === true
  const variables = []

  if (includeLocals) {
    variables.push(...getDeclaredLocalVariables(block))
  }

  if (includeArguments) {
    const procedureBlock = getEnclosingProcedureBlock(block)
    const args = getProcedureArgumentNames(block)
    for (const name of args) {
      variables.push({
        name,
        kind: 'argument',
        label: name,
        value: name,
        variableId: null,
        description: '函数参数',
        blockId: null,
        scopeKey: procedureBlock ? `procedure:${procedureBlock.id}` : 'global',
        y: -1,
      })
    }
  }

  if (includeGlobals) {
    variables.push(...getWorkspaceGlobalVariables(workspace))
  }

  const result = dedupeVariables(variables).sort((a, b) => {
    const kindWeight = { local: 0, argument: 1, global: 2 }
    const diff = (kindWeight[a.kind] || 99) - (kindWeight[b.kind] || 99)
    if (diff !== 0) return diff
    return a.name.localeCompare(b.name, 'zh-Hans-CN')
  })

  if (result.length > 0) {
    console.debug('[maa-variable] available', {
      blockType: block?.type,
      blockId: block?.id,
      values: result.map((item) => ({ name: item.name, kind: item.kind, value: item.value, blockId: item.blockId })),
    })
  }

  return result
}

export function buildVariablePickerItems(block, options = {}) {
  return getAvailableVariablesForBlock(block, options).map((item) => ({
    label: item.label,
    value: item.value,
    description: item.description,
    group: item.kind === 'local' ? '局部变量' : item.kind === 'argument' ? '函数参数' : '全局变量',
  }))
}

export function findVariableItemByValue(block, rawValue, options = {}) {
  const normalizedValue = normalizeVariableName(rawValue)
  if (!normalizedValue) return null
  const candidates = getAvailableVariablesForBlock(block, options)

  const exactValueMatch = candidates.find((item) => item.value === normalizedValue)
  if (exactValueMatch) return exactValueMatch

  const exactIdMatch = candidates.find((item) => item.variableId === normalizedValue)
  if (exactIdMatch) return exactIdMatch

  const allowLocalNameMatch = options.includeLocals !== false
  if (allowLocalNameMatch) {
    return candidates.find((item) => item.kind === 'local' && item.name === normalizedValue) || null
  }

  if (options.includeArguments === true) {
    return candidates.find((item) => item.kind === 'argument' && item.name === normalizedValue) || null
  }

  return null
}

export function getVariableFieldLabel(block, rawValue, options = {}) {
  const item = findVariableItemByValue(block, rawValue, options)
  if (item) return item.label
  return normalizeVariableName(rawValue, options.defaultLabel || '选择变量…')
}

export function openVariablePickerForBlock(block, fieldName = 'VAR', options = {}) {
  const items = buildVariablePickerItems(block, options)
  pickerActions.open({
    title: options.title || '选择变量',
    items,
    currentValue: block?.getFieldValue?.(fieldName) || null,
    emptyText: options.emptyText || '当前范围内没有可选变量',
    context: {
      kind: 'variable',
      blockId: block?.id || null,
      fieldName,
      options,
    },
    onSelect: (selectedValue) => {
      if (!selectedValue || !block || block.isDisposed?.()) return
      block.setFieldValue(selectedValue, fieldName)
      block.setWarningText(null)
    },
  })
}

export function createVariableDropdownOptions(block, options = {}) {
  const fieldName = options.fieldName || 'VAR'
  const currentItem = findVariableItemByValue(block, block?.getFieldValue?.(fieldName), options)
  const items = []
  items.push(['请选择变量', VARIABLE_PICK_VALUE])
  const isGlobalOnlyMode = currentItem?.kind === 'global'

  if (options.includeRename && isGlobalOnlyMode) {
    items.push(['重命名变量…', VARIABLE_RENAME_VALUE])
  }
  if (options.includeDelete && isGlobalOnlyMode && currentItem?.variableId) {
    items.push([`删除变量“${currentItem.label}”`, `${VARIABLE_DELETE_PREFIX}${currentItem.variableId}`])
  }
  return items
}

export function isVariableCommandValue(value) {
  return value === VARIABLE_PICK_VALUE
    || value === VARIABLE_RENAME_VALUE
    || String(value || '').startsWith(VARIABLE_DELETE_PREFIX)
}

export function handleVariableCommand(block, value, options = {}) {
  const workspace = block?.workspace || Blockly.getMainWorkspace()
  const fieldName = options.fieldName || 'VAR'
  const currentValue = block?.getFieldValue?.(fieldName) || ''
  const currentItem = findVariableItemByValue(block, currentValue, options)

  if (value === VARIABLE_PICK_VALUE) {
    openVariablePickerForBlock(block, fieldName, options)
    return currentValue
  }

  if (value === VARIABLE_RENAME_VALUE) {
    const variableId = currentItem?.variableId || normalizeVariableName(currentValue)
    const variableModel = workspace?.getVariableById?.(variableId) || null
    if (variableModel) {
      Blockly.Variables.renameVariable(workspace, variableModel)
      const blocks = workspace?.getAllBlocks?.(false) || []
      for (const item of blocks) {
        item.getField?.('VAR')?.forceRerender?.()
      }
      workspace?.getToolbox?.()?.refreshSelection?.()
    }
    return currentValue
  }

  if (String(value || '').startsWith(VARIABLE_DELETE_PREFIX)) {
    const variableId = String(value).slice(VARIABLE_DELETE_PREFIX.length)
    if (variableId) {
      const uses = workspace?.getAllBlocks?.(false)
        ?.filter((blockItem) => blockItem.getFieldValue?.(fieldName) === variableId) || []
      for (const blockItem of uses) {
        if (!blockItem || blockItem.isDisposed?.()) continue
        blockItem.dispose?.(false)
      }
      workspace?.deleteVariableById?.(variableId)
      workspace?.getToolbox?.()?.refreshSelection?.()
    }
    return currentValue
  }

  return value
}

export function validateLocalVariableReference(block, fieldName = 'VAR', options = {}) {
  if (!block || block.isInFlyout || block.isDisposed?.()) return null
  const currentValue = normalizeVariableName(block.getFieldValue?.(fieldName))
  if (!currentValue) {
    return '请选择变量'
  }
  const availableItems = getAvailableVariablesForBlock(block, options)
  const valid = availableItems.some((item) => item.value === currentValue || item.name === currentValue || item.variableId === currentValue)
  if (!valid) {
    return `变量“${currentValue}”不在当前作用域内`
  }
  return null
}
