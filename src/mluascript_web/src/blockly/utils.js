import * as Blockly from 'blockly'
import { actions, getters, state } from '../store'
import { pickerActions } from '../store/pickerState'

function asNonEmptyString(value) {
  const normalized = String(value || '').trim()
  return normalized || ''
}

function resolveBlocklyWorkspace(workspace) {
  if (workspace && typeof workspace.getAllBlocks === 'function') {
    return workspace
  }
  const mainWorkspace = Blockly.getMainWorkspace()
  if (mainWorkspace && typeof mainWorkspace.getAllBlocks === 'function') {
    return mainWorkspace
  }
  return null
}

function getWorkspaceBlocks(workspace) {
  return resolveBlocklyWorkspace(workspace)?.getAllBlocks(false) || []
}

function normalizePickerItems(items) {
  if (!Array.isArray(items)) return []
  return items
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const value = asNonEmptyString(item.value)
      const label = asNonEmptyString(item.label || item.name || value)
      if (!value && !label) return null
      return {
        ...item,
        value: value || label,
        label: label || value,
      }
    })
    .filter(Boolean)
}

const SHARED_VAR_BLOCK_TYPES = new Set([
  'shared_var_get',
  'shared_var_set',
  'shared_var_truthy',
  'shared_var_get_key',
  'shared_var_set_key',
  'shared_var_append',
  'shared_var_size',
  'shared_var_is_nil',
  'shared_var_clear',
  'shared_var_to_json',
])

const BUILTIN_SHARED_VARIABLES = []

export function getLuaScriptPickerItems(stripLuaExt = false) {
  const source = getters.luaScriptFiles?.value || getters.luaScripts?.value || []
  return normalizePickerItems(source.map((script) => {
    const rawName = asNonEmptyString(script?.name || script?.filename || script?.path)
    return {
      label: rawName,
      value: stripLuaExt ? rawName.replace(/\.lua$/, '') : rawName,
    }
  }))
}

export function getWorkspaceProcedureDefinitions(workspace = Blockly.getMainWorkspace()) {
  const resolvedWorkspace = resolveBlocklyWorkspace(workspace)
  if (!resolvedWorkspace) return []
  const definitions = []
  const seenIds = new Set()
  for (const block of getWorkspaceBlocks(resolvedWorkspace)) {
    if (!block || seenIds.has(block.id)) continue
    if (block.type !== 'procedures_defreturn' && block.type !== 'procedures_defnoreturn') continue
    const name = (block.getFieldValue('NAME') || '').trim()
    if (!name) continue
    seenIds.add(block.id)
    definitions.push({
      id: block.id,
      name,
      label: name,
      value: name,
      type: block.type,
      hasReturn: block.type === 'procedures_defreturn',
      block,
    })
  }
  return definitions
}

export function getWorkspaceFunctionPickerItems() {
  return getWorkspaceProcedureDefinitions().map(({ label, value }) => ({ label, value }))
}

export function getProcedureDefinitionByName(name, workspace = Blockly.getMainWorkspace()) {
  const normalizedName = String(name || '').trim()
  if (!normalizedName) return null
  return getWorkspaceProcedureDefinitions(workspace).find((item) => item.name === normalizedName) || null
}

export function getProcedurePickerItems(workspace = Blockly.getMainWorkspace()) {
  return normalizePickerItems(getWorkspaceProcedureDefinitions(workspace).map((item) => ({
    label: item.name,
    value: item.name,
    description: item.hasReturn ? '有返回值函数' : '无返回值函数',
  })))
}

export function applyProcedureSelectionToPickerBlock(block, procedureName) {
  if (!block) return false
  const workspace = block.workspace || Blockly.getMainWorkspace()
  const definition = getProcedureDefinitionByName(procedureName, workspace)
  if (!definition) return false

  const targetType = definition.hasReturn ? 'procedures_callreturn' : 'procedures_callnoreturn'
  const newBlock = workspace.newBlock(targetType)
  const xy = typeof block.getRelativeToSurfaceXY === 'function'
    ? block.getRelativeToSurfaceXY()
    : { x: block.x || 0, y: block.y || 0 }
  const parentConnection = block.outputConnection?.targetConnection
    || block.previousConnection?.targetConnection
  const nextConnection = block.nextConnection?.targetConnection || null

  newBlock.initSvg?.()
  newBlock.setFieldValue(procedureName, 'NAME')
  const procedureDefinitionBlock = definition.block
  const procedureInfo = procedureDefinitionBlock?.getProcedureDef?.()
  if (procedureInfo?.[1]) {
    const paramIds = Array.isArray(procedureDefinitionBlock.paramIds_)
      ? procedureDefinitionBlock.paramIds_
      : procedureInfo[1].map((_, index) => `${newBlock.id}_arg_${index}`)
    newBlock.setProcedureParameters_(procedureInfo[1], paramIds)
  }
  newBlock.render?.()
  newBlock.moveBy(xy.x, xy.y)

  if (parentConnection) {
    if (newBlock.outputConnection) {
      parentConnection.connect(newBlock.outputConnection)
    } else if (newBlock.previousConnection) {
      parentConnection.connect(newBlock.previousConnection)
    }
  }

  if (nextConnection && newBlock.nextConnection) {
    newBlock.nextConnection.connect(nextConnection)
  }

  block.dispose(false)
  newBlock.select?.()
  return true
}

export function openProcedurePickerForBlock(block) {
  const workspace = block?.workspace || Blockly.getMainWorkspace()
  const items = getProcedurePickerItems(workspace)
  pickerActions.open({
    title: '选择函数',
    items,
    currentValue: block?.getFieldValue?.('PROC_NAME') || null,
    emptyText: '请先定义函数后再调用',
    context: {
      kind: 'procedure',
      blockId: block?.id || null,
      fieldName: 'PROC_NAME',
    },
    onSelect: (selectedValue) => {
      if (!selectedValue) return
      const updated = applyProcedureSelectionToPickerBlock(block, selectedValue)
      if (!updated && block && !block.isDisposed?.()) {
        block.setWarningText('未找到对应函数定义，请重新选择')
      }
    },
  })
}

export function openBlocklyPickerForBlock(block, config) {
  const resolvedConfig = typeof config === 'function' ? config(block) : config
  const normalizedConfig = resolvedConfig && typeof resolvedConfig === 'object'
    ? {
        ...resolvedConfig,
        items: normalizePickerItems(resolvedConfig.items),
      }
    : {}
  return actions.openBlocklyPicker(normalizedConfig)
}

export function collectWorkspaceSharedVariableNames(workspace = Blockly.getMainWorkspace()) {
  const resolvedWorkspace = resolveBlocklyWorkspace(workspace)
  if (!resolvedWorkspace) return []
  const names = new Set()
  for (const block of getWorkspaceBlocks(resolvedWorkspace)) {
    if (!block || !SHARED_VAR_BLOCK_TYPES.has(block.type)) continue
    const name = String(block.getFieldValue?.('VAR_NAME') || '').trim()
    if (name) names.add(name)
  }
  return [...names].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

export function getBuiltinSharedVariableItems() {
  return BUILTIN_SHARED_VARIABLES.map((item) => ({ ...item }))
}

export function getWorkspaceSharedVariableItems(workspace = Blockly.getMainWorkspace()) {
  const builtinItems = getBuiltinSharedVariableItems()
  const builtinNames = new Set(builtinItems.map((item) => item.name))

  const workspaceNames = collectWorkspaceSharedVariableNames(workspace)
  const userCreatedNames = Array.isArray(state.userCreatedSharedVariables?.value)
    ? state.userCreatedSharedVariables.value.map((name) => asNonEmptyString(name)).filter(Boolean)
    : []

  const allUserNames = [...new Set([...workspaceNames, ...userCreatedNames])]
    .sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))

  const userItems = allUserNames
    .filter((name) => !builtinNames.has(name))
    .map((name) => ({
      name,
      label: name,
      value: name,
      group: '全局状态',
      description: workspaceNames.includes(name) ? '当前工作区已使用' : '未使用',
      builtin: false,
      readonlyName: false,
      deletable: true,
    }))

  return normalizePickerItems([
    ...builtinItems.map((item) => ({ ...item, value: item.name })),
    ...userItems,
  ])
}

function ensureSharedVariableRegistry() {
  if (!state.userCreatedSharedVariables?.value || !Array.isArray(state.userCreatedSharedVariables.value)) {
    return []
  }
  return state.userCreatedSharedVariables.value
}

function addSharedVariableName(name) {
  const normalizedName = asNonEmptyString(name)
  if (!normalizedName) return false
  const registry = ensureSharedVariableRegistry()
  if (registry.includes(normalizedName)) return false
  registry.push(normalizedName)
  if (state.sharedVariableRegistryVersion?.value !== undefined) {
    state.sharedVariableRegistryVersion.value += 1
  }
  return true
}

function removeSharedVariableName(name) {
  const normalizedName = asNonEmptyString(name)
  if (!normalizedName) return false
  const registry = ensureSharedVariableRegistry()
  const index = registry.indexOf(normalizedName)
  if (index === -1) return false
  registry.splice(index, 1)
  if (state.sharedVariableRegistryVersion?.value !== undefined) {
    state.sharedVariableRegistryVersion.value += 1
  }
  return true
}

function refreshSharedVariableFields(workspace, fieldName = 'VAR_NAME') {
  for (const item of getWorkspaceBlocks(workspace)) {
    item.getField?.(fieldName)?.forceRerender?.()
  }
}

export function renameSharedVariableInWorkspace(oldName, newName, workspace = Blockly.getMainWorkspace()) {
  const resolvedWorkspace = resolveBlocklyWorkspace(workspace)
  const source = asNonEmptyString(oldName)
  const target = asNonEmptyString(newName)
  if (!resolvedWorkspace || !source || !target || source === target) return 0
  let count = 0
  for (const block of getWorkspaceBlocks(resolvedWorkspace)) {
    if (!block || !SHARED_VAR_BLOCK_TYPES.has(block.type)) continue
    const current = asNonEmptyString(block.getFieldValue?.('VAR_NAME'))
    if (current !== source) continue
    block.setFieldValue(target, 'VAR_NAME')
    count += 1
  }
  if (count > 0) {
    removeSharedVariableName(source)
    addSharedVariableName(target)
    refreshSharedVariableFields(resolvedWorkspace)
  }
  return count
}

export function clearSharedVariableReferences(name, workspace = Blockly.getMainWorkspace()) {
  const resolvedWorkspace = resolveBlocklyWorkspace(workspace)
  const target = asNonEmptyString(name)
  if (!resolvedWorkspace || !target) return 0
  let count = 0
  for (const block of getWorkspaceBlocks(resolvedWorkspace)) {
    if (!block || !SHARED_VAR_BLOCK_TYPES.has(block.type)) continue
    const current = asNonEmptyString(block.getFieldValue?.('VAR_NAME'))
    if (current !== target) continue
    block.setFieldValue('', 'VAR_NAME')
    count += 1
  }
  if (count > 0) {
    removeSharedVariableName(target)
    refreshSharedVariableFields(resolvedWorkspace)
  }
  return count
}

export function getSharedVariableReferenceCount(name, workspace = Blockly.getMainWorkspace()) {
  const resolvedWorkspace = resolveBlocklyWorkspace(workspace)
  const target = asNonEmptyString(name)
  if (!resolvedWorkspace || !target) return 0
  let count = 0
  for (const block of getWorkspaceBlocks(resolvedWorkspace)) {
    if (!block || !SHARED_VAR_BLOCK_TYPES.has(block.type)) continue
    if (asNonEmptyString(block.getFieldValue?.('VAR_NAME')) === target) {
      count += 1
    }
  }
  return count
}

const SHARED_VARIABLE_PICK_VALUE = '__MAA_PICK_SHARED_VARIABLE__'
const SHARED_VARIABLE_RENAME_VALUE = '__MAA_RENAME_SHARED_VARIABLE__'
const SHARED_VARIABLE_DELETE_PREFIX = '__MAA_DELETE_SHARED_VARIABLE__:'

export function createSharedVariableDropdownOptions(block, options = {}) {
  const fieldName = options.fieldName || 'VAR_NAME'
  const currentValue = asNonEmptyString(block?.getFieldValue?.(fieldName))
  const workspace = resolveBlocklyWorkspace(block?.workspace)
  const allItems = getWorkspaceSharedVariableItems(workspace)

  const items = []
  items.push(['选择全局状态...', SHARED_VARIABLE_PICK_VALUE])

  const currentItem = allItems.find((item) => item.name === currentValue)
  if (currentItem && !currentItem.builtin) {
    items.push(['重命名全局状态...', SHARED_VARIABLE_RENAME_VALUE])
    items.push([`删除全局状态“${currentItem.name}”`, `${SHARED_VARIABLE_DELETE_PREFIX}${currentItem.name}`])
  }

  return items
}

export function isSharedVariableCommandValue(value) {
  return value === SHARED_VARIABLE_PICK_VALUE
    || value === SHARED_VARIABLE_RENAME_VALUE
    || String(value || '').startsWith(SHARED_VARIABLE_DELETE_PREFIX)
}

export function handleSharedVariableCommand(block, value, options = {}) {
  const workspace = resolveBlocklyWorkspace(block?.workspace)
  const fieldName = options.fieldName || 'VAR_NAME'
  const currentValue = asNonEmptyString(block?.getFieldValue?.(fieldName))

  if (value === SHARED_VARIABLE_PICK_VALUE) {
    openSharedVariablePickerForBlock(block, fieldName)
    return currentValue
  }

  if (value === SHARED_VARIABLE_RENAME_VALUE) {
    if (currentValue) {
      const newName = window.prompt('重命名全局状态', currentValue)
      const trimmedNewName = asNonEmptyString(newName)
      if (trimmedNewName && trimmedNewName !== currentValue) {
        renameSharedVariableInWorkspace(currentValue, trimmedNewName, workspace)
      }
    }
    return currentValue
  }

  if (String(value || '').startsWith(SHARED_VARIABLE_DELETE_PREFIX)) {
    const nameToDelete = asNonEmptyString(String(value).slice(SHARED_VARIABLE_DELETE_PREFIX.length))
    if (nameToDelete) {
      const uses = getWorkspaceBlocks(workspace)
        .filter((blockItem) => SHARED_VAR_BLOCK_TYPES.has(blockItem.type) && blockItem.getFieldValue?.(fieldName) === nameToDelete)
      for (const blockItem of uses) {
        if (!blockItem || blockItem.isDisposed?.()) continue
        blockItem.dispose?.(false)
      }
      removeSharedVariableName(nameToDelete)
      refreshSharedVariableFields(workspace, fieldName)
    }
    return currentValue
  }

  return value
}

export function openSharedVariablePickerForBlock(block, fieldName = 'VAR_NAME') {
  const workspace = resolveBlocklyWorkspace(block?.workspace)
  const items = getWorkspaceSharedVariableItems(workspace)
  pickerActions.open({
    title: '选择全局状态',
    items: normalizePickerItems(items.map((item) => ({
      label: item.label || item.name,
      value: item.name,
      group: item.group,
      description: item.description,
    }))),
    currentValue: block?.getFieldValue?.(fieldName) || null,
    emptyText: '暂无全局状态，可先新建一个',
    allowCreate: true,
    createButtonText: '新建全局状态',
    createPlaceholder: '输入全局状态名',
    manageButtonText: '管理状态',
    onManage: () => actions.openSharedVariableManager(),
    onCreate: (rawName) => {
      const nextName = asNonEmptyString(rawName)
      if (!nextName) {
        throw new Error('变量名不能为空')
      }
      const exists = getWorkspaceSharedVariableItems(workspace).some((item) => item.name === nextName)
      if (!exists) {
        addSharedVariableName(nextName)
      }
      if (block && !block.isDisposed?.()) {
        block.setFieldValue(nextName, fieldName)
      }
      refreshSharedVariableFields(workspace, fieldName)
      return normalizePickerItems(getWorkspaceSharedVariableItems(workspace).map((item) => ({
        label: item.label || item.name,
        value: item.name,
        group: item.group,
        description: item.description,
      })))
    },
    onSelect: (selectedValue) => {
      if (!selectedValue || !block || block.isDisposed?.()) return
      block.setFieldValue(selectedValue, fieldName)
    },
  })
}

export function getIsDarkTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark'
}
