import * as Blockly from 'blockly'
import * as ZhHans from 'blockly/msg/zh-hans'
import { ensureBlocklyBlocks } from './blocks'
import { registerCustomFields, LuaVariableField } from './fields'
import { buildToolbox } from './toolbox'
import { getIsDarkTheme } from './utils'
import { findVariableItemByValue } from './variableContext'
import { applyBlocklyZhCnLocale } from './locale'
import {
  deleteWorkspaceVariableById,
  getWorkspaceVariableById,
  getWorkspaceVariablesOfType,
} from './workspaceVariables'

const BLOCKLY_DARK_THEME = Blockly.Theme.defineTheme('maa-dark', {
  name: 'maa-dark',
  // Blockly 13 不再导出 Dark 主题 继承 Classic 以保留内置积木和分类配色
  base: Blockly.Themes.Classic,
  componentStyles: {
    workspaceBackgroundColour: '#1a1a1a',
    toolboxBackgroundColour: '#181818',
    toolboxForegroundColour: '#d6deeb',
    flyoutBackgroundColour: '#181818',
    flyoutForegroundColour: '#d6deeb',
    flyoutOpacity: 1,
  },
})

const BLOCKLY_LIGHT_THEME = Blockly.Theme.defineTheme('maa-light', {
  name: 'maa-light',
  base: Blockly.Themes.Classic,
  componentStyles: {
    workspaceBackgroundColour: '#ffffff',
    toolboxBackgroundColour: '#ffffff',
    toolboxForegroundColour: '#222222',
    flyoutBackgroundColour: '#ffffff',
    flyoutForegroundColour: '#222222',
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

export { collectBlocklyDiagnostics, workspaceToXml, workspaceToLua } from './generator'

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
  const injectionDiv = workspace.getInjectionDiv?.()
  const svg = workspace.getParentSvg()
  const toolboxDiv = injectionDiv?.querySelector('.blocklyToolbox, .blocklyToolboxDiv')

  for (const element of [injectionDiv, svg]) {
    if (!element) continue
    element.classList.toggle('blockly-theme-dark', isDark)
    element.classList.toggle('blockly-theme-light', !isDark)
  }

  if (injectionDiv) {
    injectionDiv.style.background = isDark ? '#1a1a1a' : '#ffffff'
    injectionDiv.style.border = 'none'
    injectionDiv.style.outline = 'none'
  }

  if (svg) {
    svg.style.backgroundColor = isDark ? '#1a1a1a' : '#ffffff'
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
      line.setAttribute('stroke', isDark ? '#414b5a' : '#cccccc')
      line.setAttribute('stroke-width', '2')
      line.setAttribute('stroke-opacity', isDark ? '0.8' : '1')
      line.setAttribute('fill', 'none')
    }
  } else if (mainBackground) {
    mainBackground.setAttribute('fill', isDark ? '#1a1a1a' : '#ffffff')
    mainBackground.style.fill = isDark ? '#1a1a1a' : '#ffffff'
  }

  if (toolboxDiv) {
    toolboxDiv.style.background = isDark ? '#181818' : '#ffffff'
    toolboxDiv.style.color = isDark ? '#d6deeb' : '#222222'
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
      colour: isDark ? '#313846' : '#cccccc',
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
      Blockly.Xml.domToWorkspace(dom, workspace)
    } catch (error) {
      console.warn('恢复 Blockly 工作区失败', error)
    } finally {
      Blockly.Events.enable()
    }
    patchCoreVariableBlocks(workspace)
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

export function updateBlocklyTheme(workspace, isDark) {
  if (!workspace) return
  workspace.setTheme(getBlocklyTheme(isDark))
  if (workspace.options?.grid) {
    workspace.options.grid.colour = isDark ? '#414b5a' : '#cccccc'
  }
  window.requestAnimationFrame(() => {
    Blockly.svgResize(workspace)
    workspace.getToolbox()?.refreshSelection?.()
    applyBlocklyDomTheme(workspace)
  })
}
