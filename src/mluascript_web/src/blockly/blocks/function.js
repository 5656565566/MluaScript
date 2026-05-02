import * as Blockly from 'blockly'
import { luaOrder, PICKER_ICON_TYPE } from '../constants'
import { validateLocalVariableReference } from '../variableContext'
import { MaaPickerIcon } from '../fields'
import { state, actions } from '../../store'

function getEnclosingProcedureBlock(block) {
  if (!block?.workspace) return null
  let parent = block.getSurroundParent()
  while (parent) {
    if (parent.type === 'procedures_defnoreturn' || parent.type === 'procedures_defreturn') {
      return parent
    }
    parent = parent.getSurroundParent()
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
  return args
    .map((arg) => String(arg || '').trim())
    .filter((arg, index, array) => arg && array.indexOf(arg) === index)
}

function getProcedureArgumentName(block) {
  const selectedArg = String(block?.getFieldValue?.('VAR') || '').trim()
  if (!selectedArg) return ''
  const validArgs = getProcedureArgumentNames(block)
  return validArgs.includes(selectedArg) ? selectedArg : ''
}

function attachLocalVariableWarning(block, options = {}) {
  block.setOnChange(() => {
    if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
    const warning = validateLocalVariableReference(block, 'VAR', options)
    block.setWarningText(warning)
  })
}

function buildProcedureArgDropdownOptions(block, field) {
  if (!block?.workspace) return [['无参数', '']]
  const args = getProcedureArgumentNames(block)
  let options = []
  if (args.length > 0) {
    options = args.map((arg) => [arg, arg])
  } else {
    options = getEnclosingProcedureBlock(block) ? [['无参数', '']] : [['不在函数内', '']]
  }

  const currentVal = field?.getValue?.() || field?.__pendingValue
  if (currentVal && typeof currentVal === 'string') {
    if (!options.some((opt) => opt[1] === currentVal)) {
      options.push([currentVal, currentVal])
    }
  }

  return options
}

function syncProcedureArgField(block) {
  const field = block?.getField?.('VAR')
  if (!field) return
  field.menuGenerator_ = function() { return buildProcedureArgDropdownOptions(block, this) }
  field.generatedOptions_ = null
  field.forceRerender?.()
}

function attachProcedureArgumentWarning(block) {
  block.setOnChange(function() {
    if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
    syncProcedureArgField(block)
    const validArgs = getProcedureArgumentNames(block)
    const inProcedure = !!getEnclosingProcedureBlock(block)
    if (!inProcedure) {
      block.setWarningText('此块只能在函数定义内部使用。')
      return
    }
    const currentVar = block.getFieldValue('VAR')
    if (currentVar && !validArgs.includes(currentVar)) {
      block.setWarningText(`参数 "${currentVar}" 不存在于当前函数中。`)
    } else {
      block.setWarningText(null)
    }
  })
}

function getTemplateVarPickerItems(workspace) {
  let data = {}
  if (workspace) {
    const blocks = workspace.getAllBlocks(false)
    const templateBlock = blocks.find(b => b.type === 'maa_template_config')
    if (templateBlock) {
      try {
        data = JSON.parse(templateBlock.getFieldValue('TEMPLATE_JSON') || '{}')
      } catch (e) {}
    }
  }

  const vars = data.vars || {}
  const result = []
  for (const [key, field] of Object.entries(vars)) {
    result.push({
      label: field?.t ? `${field.t} (${key})` : key,
      rawName: field?.t || key,
      value: key,
      desc: field?.note || '顶层变量',
    })
    for (const child of field?.children || []) {
      if (!child?.k) continue
      result.push({
        label: child?.t ? `${child.t} (${child.k})` : child.k,
        rawName: child?.t || child.k,
        value: child.k,
        desc: `来自 ${field?.t || key}`,
      })
    }
    for (const option of field?.oneOf || []) {
      for (const child of option?.children || []) {
        if (!child?.k) continue
        result.push({
          label: child?.t ? `${child.t} (${child.k})` : child.k,
          rawName: child?.t || child.k,
          value: child.k,
          desc: `来自 ${field?.t || key} / ${option?.t || option?.v || ''}`,
        })
      }
    }
  }
  return result
}

function attachTemplateArgPicker(block, fieldName = 'TPL_VAR', labelFieldName = 'TPL_VAR_LABEL') {
  if (block.getIcon(PICKER_ICON_TYPE)) return
  const icon = new MaaPickerIcon(block, () => null)
  icon.onClick = () => {
    const items = getTemplateVarPickerItems(block.workspace)
    actions.openBlocklyPicker({
      title: '选择模板参数',
      summary: '选择后会生成 args.xxx 语法。',
      items,
      currentValue: block.getFieldValue(fieldName) || null,
      emptyText: '当前模板里没有可选参数',
      onSelect: (selectedValue) => {
        if (!selectedValue) return
        const selected = items.find(item => item.value === selectedValue)
        block.setFieldValue(selectedValue, fieldName)
        const label = selected ? (selected.rawName || selected.label || selectedValue) : selectedValue
        block.setFieldValue(label, labelFieldName)
        block.setWarningText(null)
      },
    })
  }
  block.addIcon(icon)
}

export const functionBlocks = [
  {
    type: 'procedure_arg_get',
    category: null,
    init(block) {
      const dropdown = new Blockly.FieldDropdown(function() {
        return buildProcedureArgDropdownOptions(block, this)
      })
      const originalValidate = dropdown.doClassValidation_.bind(dropdown)
      dropdown.doClassValidation_ = function(newValue) {
        this.__pendingValue = newValue
        const result = originalValidate(newValue)
        this.__pendingValue = undefined
        return result
      }

      block.appendDummyInput()
        .appendField('函数参数')
        .appendField(dropdown, 'VAR')
      block.setOutput(true, null)
      block.setColour(290)
      block.setTooltip('获取当前函数的参数。只能在函数内部使用。')
      syncProcedureArgField(block)
      attachProcedureArgumentWarning(block)
    },
    generator(block) {
      const varName = getProcedureArgumentName(block)
      if (!varName) return ['nil', luaOrder]
      return [varName, luaOrder]
    }
  },
  {
    type: 'template_arg_get',
    category: null,
    init(block) {
      block.appendDummyInput('TOPROW')
        .appendField('模板参数')
        .appendField('未选择', 'TPL_VAR_LABEL')
      block.appendDummyInput('HIDDEN')
        .appendField(new Blockly.FieldTextInput(''), 'TPL_VAR')
        .setVisible(false)
      block.setOutput(true, null)
      block.setColour(290)
      block.setTooltip('读取模板参数，生成 args.xxx。')
      attachTemplateArgPicker(block)
      block.setOnChange((event) => {
        if (!block.workspace || block.isInFlyout || block.isDisposed?.()) return
        
        // 只在创建、修改、或者状态恢复时更新文本
        if (event && event.type !== Blockly.Events.BLOCK_CREATE && event.type !== Blockly.Events.BLOCK_CHANGE && event.type !== Blockly.Events.FINISHED_LOADING) {
          return
        }

        const currentValue = block.getFieldValue('TPL_VAR') || ''
        if (!currentValue) {
          if (block.getFieldValue('TPL_VAR_LABEL') !== '未选择') {
            block.setFieldValue('未选择', 'TPL_VAR_LABEL')
          }
          block.setWarningText('请点击齿轮选择模板参数')
          return
        }
        const items = getTemplateVarPickerItems(block.workspace)
        const selected = items.find(item => item.value === currentValue)
        const label = selected ? (selected.rawName || selected.label || currentValue) : currentValue
        
        if (block.getFieldValue('TPL_VAR_LABEL') !== label) {
          block.setFieldValue(label, 'TPL_VAR_LABEL')
        }
        block.setWarningText(null)
      })
    },
    generator(block) {
      const key = String(block.getFieldValue('TPL_VAR') || '').trim()
      if (!key) return ['nil', luaOrder]
      return [`args.${key}`, luaOrder]
    }
  },
  {
    type: 'procedure_arg_set',
    category: null,
    init(block) {
      const dropdown = new Blockly.FieldDropdown(function() {
        return buildProcedureArgDropdownOptions(block, this)
      })
      const originalValidate = dropdown.doClassValidation_.bind(dropdown)
      dropdown.doClassValidation_ = function(newValue) {
        this.__pendingValue = newValue
        const result = originalValidate(newValue)
        this.__pendingValue = undefined
        return result
      }

      block.appendValueInput('VALUE')
        .appendField('赋值函数参数')
        .appendField(dropdown, 'VAR')
        .appendField('为')
      block.setPreviousStatement(true, null)
      block.setNextStatement(true, null)
      block.setColour(290)
      block.setTooltip('修改当前函数的参数值。只能在函数内部使用。')
      syncProcedureArgField(block)
      attachProcedureArgumentWarning(block)
    },
    generator(block, generator) {
      const varName = getProcedureArgumentName(block)
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      if (!varName) return ''
      return `${varName} = ${value}\n`
    }
  },
  {
    type: 'local_var_declare',
    category: null,
    definition: {
      message0: '声明局部变量 %1 初始化为 %2',
      args0: [
        { type: 'field_input', name: 'VAR', text: 'item' },
        { type: 'input_value', name: 'VALUE' }
      ],
      style: 'variable_blocks',
      previousStatement: null,
      nextStatement: null,
      tooltip: '声明一个仅在当前代码块内有效的局部变量',
      helpUrl: '',
    },
    generator(block, generator) {
      const varName = block.getFieldValue('VAR') || 'item'
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      const safeName = generator.nameDB_ ? generator.nameDB_.getName(varName, Blockly.VARIABLE_CATEGORY_NAME || 'VARIABLE') : varName
      return `local ${safeName} = ${value}\n`
    }
  },
  {
    type: 'local_var_get',
    category: null,
    definition: {
      style: 'variable_blocks',
      message0: '局部变量 %1',
      args0: [
        {
          type: 'field_dropdown',
          name: 'VAR',
          options: [['选择变量…', '']]
        }
      ],
      output: null,
      tooltip: '获取局部变量的值',
      helpUrl: '',
    },
    init(block) {
      block.getInput('DUMMY0')?.removeField('VAR', true)
      block.getInput('DUMMY0')?.appendField(new Blockly.Field.fromJson({
        type: 'field_variable_custom',
        fieldName: 'VAR',
        includeGlobals: true,
        includeLocals: true,
        includeArguments: true,
        includeRename: false,
        includeDelete: false,
        title: '选择局部变量',
        emptyText: '当前作用域内没有可选变量',
      }), 'VAR')
      attachLocalVariableWarning(block, {
        includeGlobals: true,
        includeLocals: true,
        includeArguments: true,
      })
    },
    generator(block, generator) {
      const varName = block.getFieldValue('VAR') || 'item'
      const safeName = generator.nameDB_ ? generator.nameDB_.getName(varName, Blockly.VARIABLE_CATEGORY_NAME || 'VARIABLE') : varName
      return [safeName, luaOrder]
    }
  },
  {
    type: 'local_var_set',
    category: null,
    definition: {
      style: 'variable_blocks',
      message0: '赋值局部变量 %1 为 %2',
      args0: [
        {
          type: 'field_dropdown',
          name: 'VAR',
          options: [['选择变量…', '']]
        },
        { type: 'input_value', name: 'VALUE' }
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '修改已声明的局部变量的值',
      helpUrl: '',
    },
    init(block) {
      block.getInput('DUMMY0')?.removeField('VAR', true)
      block.getInput('DUMMY0')?.appendField(new Blockly.Field.fromJson({
        type: 'field_variable_custom',
        fieldName: 'VAR',
        includeGlobals: true,
        includeLocals: true,
        includeArguments: true,
        includeRename: false,
        includeDelete: false,
        title: '选择局部变量',
        emptyText: '当前作用域内没有可选变量',
      }), 'VAR')
      attachLocalVariableWarning(block, {
        includeGlobals: true,
        includeLocals: true,
        includeArguments: true,
      })
    },
    generator(block, generator) {
      const varName = block.getFieldValue('VAR') || 'item'
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      const safeName = generator.nameDB_ ? generator.nameDB_.getName(varName, Blockly.VARIABLE_CATEGORY_NAME || 'VARIABLE') : varName
      return `${safeName} = ${value}\n`
    }
  },
]
