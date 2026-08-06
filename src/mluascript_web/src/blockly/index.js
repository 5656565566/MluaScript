import * as Blockly from 'blockly'
import * as ZhHans from 'blockly/msg/zh-hans'
import { ensureBlocklyBlocks } from './blocks'
import { registerCustomFields, LuaVariableField } from './fields'
import { buildToolbox } from './toolbox'
import { getIsDarkTheme } from './utils'
import { findVariableItemByValue } from './variableContext'
import { applyBlocklyZhCnLocale } from './locale'
import { getBlocklyUiPalette } from '../app/theme'
import { collectBlocklyDiagnostics, workspaceToLua } from './generator'
import { migrateLegacyProjectModuleCallXml, restoreProjectModuleCallState } from './projectModuleCall.js'
import { restoreSerializedPickerLabel } from './pickerBlockState.js'
import {
  deleteWorkspaceVariableById,
  getWorkspaceVariableById,
  getWorkspaceVariablesOfType,
} from './workspaceVariables'

const blocklyDarkUi = getBlocklyUiPalette(true)
const blocklyLightUi = getBlocklyUiPalette(false)

const BLOCKLY_DARK_THEME = Blockly.Theme.defineTheme('maa-dark', {
  name: 'maa-dark',
  // Blockly 13 不再导出 Dark 主题 继承 Classic 以保留内置积木和分类配色
  base: Blockly.Themes.Classic,
  componentStyles: {
    workspaceBackgroundColour: blocklyDarkUi.workspace,
    toolboxBackgroundColour: blocklyDarkUi.toolbox,
    toolboxForegroundColour: blocklyDarkUi.text,
    flyoutBackgroundColour: blocklyDarkUi.toolbox,
    flyoutForegroundColour: blocklyDarkUi.text,
    flyoutOpacity: 1,
  },
})

const BLOCKLY_LIGHT_THEME = Blockly.Theme.defineTheme('maa-light', {
  name: 'maa-light',
  base: Blockly.Themes.Classic,
  componentStyles: {
    workspaceBackgroundColour: blocklyLightUi.workspace,
    toolboxBackgroundColour: blocklyLightUi.toolbox,
    toolboxForegroundColour: blocklyLightUi.text,
    flyoutBackgroundColour: blocklyLightUi.toolbox,
    flyoutForegroundColour: blocklyLightUi.text,
    flyoutOpacity: 1,
  },
})

function getBlocklyTheme(isDark) {
  return isDark ? BLOCKLY_DARK_THEME : BLOCKLY_LIGHT_THEME
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

function buildFilteredVariableFlyout(workspace) {
  const xmlItems = []
  const button = document.createElement('button')
  button.setAttribute('text', '创建全局变量…')
  button.setAttribute('callbackKey', 'CREATE_VARIABLE')
  workspace.registerButtonCallback('CREATE_VARIABLE', (buttonBlock) => {
    Blockly.Variables.createVariableButtonHandler(buttonBlock.getTargetWorkspace())
  })
  xmlItems.push(button)

  const argumentIds = getProcedureArgumentVariableIds(workspace)
  const variables = getWorkspaceVariablesOfType(workspace)
    .filter((variable) => !argumentIds.has(variable.getId()))
  const latestVariable = variables[variables.length - 1] || null

  if (Blockly.Blocks.local_var_declare) {
    const localDeclareBlock = Blockly.utils.xml.createElement('block')
    localDeclareBlock.setAttribute('type', 'local_var_declare')
    localDeclareBlock.setAttribute('gap', '8')
    xmlItems.push(localDeclareBlock)
  }

  if (Blockly.Blocks.variables_set) {
    const setBlock = Blockly.utils.xml.createElement('block')
    setBlock.setAttribute('type', 'variables_set')
    setBlock.setAttribute('gap', Blockly.Blocks.math_change ? '8' : '24')
    xmlItems.push(setBlock)
  }

  if (Blockly.Blocks.math_change) {
    const changeBlock = Blockly.utils.xml.createElement('block')
    changeBlock.setAttribute('type', 'math_change')
    changeBlock.setAttribute('gap', Blockly.Blocks.variables_get ? '20' : '8')
    xmlItems.push(changeBlock)
  }

  if (Blockly.Blocks.variables_get) {
    const getBlock = Blockly.utils.xml.createElement('block')
    getBlock.setAttribute('type', 'variables_get')
    getBlock.setAttribute('gap', '8')
    xmlItems.push(getBlock)
  }

  return xmlItems
}

export { collectBlocklyDiagnostics, workspaceToLua }
export { workspaceToXml } from './generator'

applyBlocklyZhCnLocale(Blockly, ZhHans)

registerCustomFields()

function getProcedureDropdownOptions(workspace) {
  const blocks = typeof workspace?.getAllBlocks === 'function'
    ? workspace.getAllBlocks(false)
    : typeof workspace?.getTopBlocks === 'function'
      ? workspace.getTopBlocks(false)
      : []
  const names = blocks
    .filter((block) => block?.type === 'procedures_defnoreturn' || block?.type === 'procedures_defreturn')
    .map((block) => (block.getFieldValue('NAME') || '').trim())
    .filter(Boolean)

  const uniqueNames = [...new Set(names)]
  if (!uniqueNames.length) {
    return [['函数', '函数']]
  }
  return uniqueNames.map((name) => [name, name])
}

function refreshFunctionReferenceDropdown(workspace) {
  if (!workspace) return
  const blocks = workspace.getAllBlocks(false).filter((block) =>
    block?.type === 'lua_function_reference'
  )
  for (const block of blocks) {
    const field = block.getField('FUNC_NAME')
    if (!field || typeof field.menuGenerator_ === 'undefined') continue
    const currentValue = field.getValue?.() || ''
    const options = getProcedureDropdownOptions(workspace)
    field.menuGenerator_ = options
    const hasCurrent = options.some((option) => option[1] === currentValue)
    field.setValue(hasCurrent ? currentValue : options[0][1])
    block.setWarningText(options.length === 1 && options[0][1] === '函数' ? '请先定义函数' : null)
  }
}

function applyBlocklyDomTheme(workspace) {
  if (!workspace) return

  const isDark = getIsDarkTheme()
  const ui = getBlocklyUiPalette(isDark)
  const injectionDiv = workspace.getInjectionDiv?.()
  const svg = workspace.getParentSvg()
  const toolboxDiv = injectionDiv?.querySelector('.blocklyToolbox, .blocklyToolboxDiv')

  for (const element of [injectionDiv, svg]) {
    if (!element) continue
    element.classList.toggle('blockly-theme-dark', isDark)
    element.classList.toggle('blockly-theme-light', !isDark)
  }

  if (injectionDiv) {
    injectionDiv.style.background = ui.workspace
    injectionDiv.style.border = 'none'
    injectionDiv.style.outline = 'none'
  }

  if (svg) {
    svg.style.backgroundColor = ui.workspace
    svg.style.border = 'none'
    svg.style.outline = 'none'
  }

  const grid = workspace.getGrid?.()
  const gridPattern = grid?.pattern || svg?.querySelector('pattern')
  const mainBackground = svg?.querySelector('.blocklyMainBackground')
  if (gridPattern) {
    const patternId = gridPattern.id
    if (mainBackground && patternId) {
      mainBackground.setAttribute('fill', `url(#${patternId})`)
      mainBackground.style.fill = `url(#${patternId})`
    }
    const lines = gridPattern.querySelectorAll('line, path')
    for (const line of lines) {
      line.setAttribute('stroke', ui.grid)
      line.setAttribute('stroke-width', '2')
      line.setAttribute('stroke-opacity', isDark ? '0.8' : '1')
      line.setAttribute('fill', 'none')
    }
  } else if (mainBackground) {
    mainBackground.setAttribute('fill', ui.workspace)
    mainBackground.style.fill = ui.workspace
  }

  if (toolboxDiv) {
    toolboxDiv.style.background = ui.toolbox
    toolboxDiv.style.color = ui.text
  }
}

function patchCoreVariableBlocks(workspace) {
  const blockConfigs = {
    variables_get: {
      includeGlobals: true,
      includeLocals: true,
      includeArguments: false,
      includeRename: true,
      includeDelete: true,
      title: '选择变量',
      emptyText: '当前范围内没有可选变量',
      defaultLabel: '选择变量…',
    },
    variables_set: {
      includeGlobals: true,
      includeLocals: true,
      includeArguments: false,
      includeRename: true,
      includeDelete: true,
      title: '选择变量',
      emptyText: '当前范围内没有可选变量',
      defaultLabel: '选择变量…',
    },
    math_change: {
      includeGlobals: true,
      includeLocals: true,
      includeArguments: false,
      includeRename: true,
      includeDelete: true,
      title: '选择变量',
      emptyText: '当前范围内没有可选变量',
      defaultLabel: '选择变量…',
    },
  }

  const configureVariableField = (block, options = {}) => {
    const firstInput = block.inputList?.[0]
    const oldField = block.getField('VAR')
    if (!firstInput || !oldField) return
    firstInput.removeField('VAR', true)
    const field = new LuaVariableField(null, {
      fieldName: 'VAR',
      ...options,
    })
    firstInput.appendField(field, 'VAR')
    const currentValue = oldField.getValue?.() || oldField.variable?.getId?.() || ''
    if (currentValue) {
      field.setValue(currentValue)
    }
  }

  const applyVariableFieldPatch = (block) => {
    if (!block || block.isDisposed?.() || block.__luaVariableFieldPatched) return
    if (!block.getField('VAR')) return
    const config = blockConfigs[block.type]
    if (!config) return
    configureVariableField(block, config)
    block.__luaVariableFieldPatched = true
    block.setOnChange(() => {
      if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
      const currentValue = block.getFieldValue('VAR')
      const variableItem = findVariableItemByValue(block, currentValue, blockConfigs[block.type])
      if (!currentValue) {
        block.setWarningText('请先选择一个变量')
        return
      }
      if (!variableItem) {
        block.setWarningText(`变量“${currentValue}”不在当前作用域内`)
        return
      }
      block.setWarningText(null)
    })
  }

  const patchBlockPrototype = (blockType) => {
    const originalInit = Blockly.Blocks[blockType]?.init
    if (!originalInit || Blockly.Blocks[blockType].__maaPatched) return
    Blockly.Blocks[blockType].init = function() {
      originalInit.call(this)
      applyVariableFieldPatch(this)
    }
    Blockly.Blocks[blockType].__maaPatched = true
  }

  patchBlockPrototype('variables_get')
  patchBlockPrototype('variables_set')
  patchBlockPrototype('math_change')

  for (const block of workspace?.getAllBlocks?.(false) || []) {
    if (block.type === 'variables_get' || block.type === 'variables_set' || block.type === 'math_change') {
      applyVariableFieldPatch(block)
    }
  }
}

export function createBlocklyWorkspace(element, initialXml = '') {
  ensureBlocklyBlocks()
  
  const isDark = getIsDarkTheme()
  
  const workspace = Blockly.inject(element, {
    toolbox: buildToolbox(),
    trashcan: true,
    sounds: false,
    renderer: 'zelos',
    theme: getBlocklyTheme(isDark),
    grid: {
      spacing: 24,
      length: 3,
      colour: getBlocklyUiPalette(isDark).initialGrid,
      snap: true,
    },
    zoom: {
      controls: true,
      wheel: true,
      startScale: 0.95,
      maxScale: 2,
      minScale: 0.5,
      scaleSpeed: 1.1,
    },
    move: {
      drag: true,
      wheel: true,
    },
  })

  patchCoreVariableBlocks(workspace)

  workspace.registerToolboxCategoryCallback(Blockly.VARIABLE_CATEGORY_NAME, buildFilteredVariableFlyout)

  applyBlocklyDomTheme(workspace)

  window.requestAnimationFrame(() => {
    Blockly.svgResize(workspace)
    workspace.getToolbox()?.refreshSelection()
  })

  if (initialXml) {
    try {
      Blockly.Events.disable()
      const dom = Blockly.utils.xml.textToDom(initialXml)
      migrateLegacyProjectModuleCallXml(dom)
      Blockly.Xml.domToWorkspace(dom, workspace)
    } catch (error) {
      console.warn('恢复 Blockly 工作区失败', error)
    } finally {
      Blockly.Events.enable()
    }
    patchCoreVariableBlocks(workspace)
  }

  // 兼容尚未带 mutation 的旧保存文件：字段加载完成后补建标签和动态参数输入。
  for (const block of workspace.getAllBlocks(false)) {
    if (block.type === 'lua_project_module_call_stmt' || block.type === 'lua_project_module_call_expr') {
      restoreProjectModuleCallState(block)
    } else {
      restoreSerializedPickerLabel(block)
    }
  }

  let previousArgumentIds = getProcedureArgumentVariableIds(workspace)
  const orphanedArgumentIds = new Set()

  workspace.addChangeListener((event) => {
    if (event?.isUiEvent) return
    refreshFunctionReferenceDropdown(workspace)
    if (event?.type === Blockly.Events.BLOCK_CREATE || event?.type === Blockly.Events.BLOCK_CHANGE) {
      patchCoreVariableBlocks(workspace)
    }
    if (event?.type === Blockly.Events.BLOCK_CHANGE || event?.type === Blockly.Events.BLOCK_CREATE || event?.type === Blockly.Events.BLOCK_DELETE) {
      workspace.getToolbox()?.refreshSelection()
    }

    if (
      event?.type === Blockly.Events.BLOCK_CHANGE ||
      event?.type === Blockly.Events.BLOCK_DELETE ||
      event?.type === Blockly.Events.VAR_CREATE ||
      event?.type === Blockly.Events.VAR_DELETE ||
      event?.type === Blockly.Events.BLOCK_CREATE
    ) {
      const currentArgumentIds = getProcedureArgumentVariableIds(workspace)
      for (const id of previousArgumentIds) {
        if (!currentArgumentIds.has(id)) {
          orphanedArgumentIds.add(id)
        }
      }
      for (const id of orphanedArgumentIds) {
        if (currentArgumentIds.has(id)) {
          orphanedArgumentIds.delete(id)
          continue
        }
        const variable = getWorkspaceVariableById(workspace, id)
        if (!variable) {
          orphanedArgumentIds.delete(id)
          continue
        }
        const uses = Blockly.Variables.getVariableUsesById(workspace, id)
        if (!uses || uses.length === 0) {
          try {
            deleteWorkspaceVariableById(workspace, id)
          } catch (e) {}
          orphanedArgumentIds.delete(id)
        }
      }
      previousArgumentIds = currentArgumentIds
    }
  })
  refreshFunctionReferenceDropdown(workspace)
  workspace.getToolbox()?.refreshSelection()

  return workspace
}

export function compileBlocklyXml(xmlText) {
  // 打包多 XML 时使用无界面工作区，生成规则与当前编辑器保持一致。
  ensureBlocklyBlocks()
  const workspace = new Blockly.Workspace()
  try {
    patchCoreVariableBlocks(workspace)
    const dom = Blockly.utils.xml.textToDom(String(xmlText || ''))
    Blockly.Xml.domToWorkspace(dom, workspace)
    patchCoreVariableBlocks(workspace)
    refreshFunctionReferenceDropdown(workspace)
    const diagnostics = collectBlocklyDiagnostics(workspace)
    if (diagnostics.length) return { code: '', diagnostics, stale: true }
    return { code: workspaceToLua(workspace), diagnostics: [], stale: false }
  } catch (error) {
    return {
      code: '',
      diagnostics: [{ severity: 'error', message: error?.message || 'Lua 生成失败' }],
      stale: true,
    }
  } finally {
    workspace.dispose()
  }
}

export function updateBlocklyTheme(workspace, isDark) {
  if (!workspace) return
  workspace.setTheme(getBlocklyTheme(isDark))
  if (workspace.options?.grid) {
    workspace.options.grid.colour = getBlocklyUiPalette(isDark).grid
  }
  window.requestAnimationFrame(() => {
    Blockly.svgResize(workspace)
    workspace.getToolbox()?.refreshSelection?.()
    applyBlocklyDomTheme(workspace)
  })
}
