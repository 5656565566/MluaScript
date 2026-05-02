import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'
import { findVariableItemByValue } from './variableContext'

function isInvalidVariableBlock(block) {
  if (!block || block.isDisposed?.()) return false
  if (!['variables_get', 'variables_set', 'math_change'].includes(block.type)) return false
  const currentValue = block.getFieldValue?.('VAR') || ''
  if (!currentValue) return true
  const variableItem = findVariableItemByValue(block, currentValue, {
    includeGlobals: true,
    includeLocals: true,
    includeArguments: false,
  })
  return !variableItem
}

function wrapVariableBlockGenerators() {
  const variableBlockTypes = ['variables_get', 'variables_set', 'math_change']
  const originalGenerators = new Map()

  for (const type of variableBlockTypes) {
    const original = luaGenerator.forBlock[type]
    if (typeof original !== 'function') continue
    if (original.__maaWarningWrapped) continue
    originalGenerators.set(type, original)
  }

  for (const [type, original] of originalGenerators.entries()) {
    const wrapped = function(block, generator) {
      if (isInvalidVariableBlock(block)) {
        if (type === 'variables_get') {
          return ['nil', luaGenerator.ORDER_ATOMIC]
        }
        return ''
      }
      return original.call(this, block, generator)
    }
    wrapped.__maaWarningWrapped = true
    luaGenerator.forBlock[type] = wrapped
  }
}

export function workspaceToXml(workspace) {
  const dom = Blockly.Xml.workspaceToDom(workspace)

  // 由于 MaaVariableField（FieldDropdown）替换了原生 FieldVariable，
  // Blockly 的 workspaceToDom 不会自动收集这些变量到 <variables> 元素。
  // 这里手动确保所有工作区变量都被序列化。
  const allVars = workspace.getAllVariables?.() || []
  if (allVars.length > 0) {
    let variablesElement = dom.querySelector('variables')
    if (!variablesElement) {
      variablesElement = Blockly.utils.xml.createElement('variable' + 's')
      // 插入到 dom 的最前面
      if (dom.firstChild) {
        dom.insertBefore(variablesElement, dom.firstChild)
      } else {
        dom.appendChild(variablesElement)
      }
    }
    const existingIds = new Set()
    for (const child of variablesElement.children) {
      const id = child.getAttribute('id')
      if (id) existingIds.add(id)
    }
    for (const variable of allVars) {
      const varId = variable.getId()
      if (existingIds.has(varId)) continue
      const varElement = Blockly.utils.xml.createElement('variable')
      varElement.setAttribute('id', varId)
      if (variable.type) {
        varElement.setAttribute('type', variable.type)
      }
      varElement.textContent = variable.name
      variablesElement.appendChild(varElement)
    }
  }

  return Blockly.Xml.domToText(dom)
}

function collectModuleExportFunctions(workspace) {
  if (!workspace) return []
  const exportBlock = workspace
    .getTopBlocks(false)
    .find((block) => block?.type === 'lua_module_export_function')
  if (!exportBlock) return []
  try {
    const values = JSON.parse(exportBlock.getFieldValue('FUNC_VALUES') || '[]')
    return Array.isArray(values) ? values.map((item) => String(item || '').trim()).filter(Boolean) : []
  } catch {
    return []
  }
}

function collectDefinedProcedureNames(workspace) {
  if (!workspace) return new Set()
  return new Set(
    workspace
      .getTopBlocks(false)
      .filter((block) => block?.type === 'procedures_defnoreturn' || block?.type === 'procedures_defreturn')
      .map((block) => (block.getFieldValue('NAME') || '').trim())
      .filter(Boolean)
  )
}

function detectModuleExport(workspace) {
  if (!workspace) return false
  return workspace
    .getTopBlocks(false)
    .some((block) => block?.type === 'lua_module_export_function')
}

function buildModuleExportCode(workspace, generator) {
  const exportNames = collectModuleExportFunctions(workspace)
  if (!exportNames.length) return ''

  const definedNames = collectDefinedProcedureNames(workspace)
  const resolvedNames = []

  for (const rawName of exportNames) {
    if (!definedNames.has(rawName)) {
      resolvedNames.push({ rawName, generatedName: null })
      continue
    }
    const generatedName = generator.nameDB_
      ? generator.nameDB_.getName(rawName, Blockly.PROCEDURE_CATEGORY_NAME || 'PROCEDURE')
      : rawName
    resolvedNames.push({ rawName, generatedName })
  }

  const missingNames = resolvedNames.filter((item) => !item.generatedName).map((item) => item.rawName)
  if (missingNames.length) {
    return `-- 以下导出目标不是已定义函数: ${missingNames.join(', ')}\n`
  }

  const uniqueResolvedNames = []
  const seen = new Set()
  for (const item of resolvedNames) {
    if (!seen.has(item.generatedName)) {
      seen.add(item.generatedName)
      uniqueResolvedNames.push(item.generatedName)
    }
  }

  const exportBody = uniqueResolvedNames.map((name) => `  ${name} = ${name}`).join(',\n')
  return `\nreturn {\n${exportBody}\n}\n`
}

export function workspaceToLua(workspace) {
  const hasModuleExport = detectModuleExport(workspace)
  wrapVariableBlockGenerators()

  try {
    const code = luaGenerator.workspaceToCode(workspace)
    if (hasModuleExport) {
      const sanitizedCode = code
        .split('\n')
        .filter((line) => !line.trimStart().startsWith('-- __maa_export_function__:'))
        .join('\n')
        .trimEnd()
      const exportCode = buildModuleExportCode(workspace, luaGenerator)
      const finalCode = `${sanitizedCode}${exportCode}`.trim()
      return finalCode || '-- 请先编排 Blockly 拼图块'
    }

    const rawCode = luaGenerator.workspaceToCode(workspace)
    const lines = rawCode.split('\n')
    const templateLines = []
    const bodyLines = []
    let inTemplateBlock = false
    for (const line of lines) {
      const trimmed = line.trimStart()
      if (trimmed.startsWith('-- @mlua-template:start')) {
        inTemplateBlock = true
        templateLines.push(line)
        continue
      }
      if (inTemplateBlock) {
        templateLines.push(line)
        if (trimmed.startsWith('-- @mlua-template:end')) {
          inTemplateBlock = false
        }
        continue
      }
      bodyLines.push(line)
    }
    const mergedCode = `${templateLines.join('\n')}${templateLines.length ? '\n' : ''}${bodyLines.join('\n')}`.trim()
    return mergedCode || '-- 请先编排 Blockly 拼图块'
  } catch (error) {
    console.error('生成 Blockly Lua 代码失败', error)
    return '-- 生成 Lua 代码失败'
  }
}
