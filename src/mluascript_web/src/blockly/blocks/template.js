import * as Blockly from 'blockly'
import { luaOrder, PICKER_ICON_TYPE } from '../constants'
import { MaaPickerIcon } from '../fields'
import { attachBlockSemanticWarning, getBlockSemanticDiagnostic } from '../blockSemanticDiagnostics'
import { actions, state } from '../../store'

function cleanTemplateData(data) {
  if (Array.isArray(data)) {
    const arr = data.map(cleanTemplateData).filter(item => item !== null && item !== undefined && item !== '')
    return arr.length > 0 ? arr : undefined
  } else if (data !== null && typeof data === 'object') {
    const cleaned = {}
    let hasKeys = false
    for (const [key, value] of Object.entries(data)) {
      const cleanedValue = cleanTemplateData(value)
      if (cleanedValue !== null && cleanedValue !== undefined && cleanedValue !== '') {
        cleaned[key] = cleanedValue
        hasKeys = true
      }
    }
    return hasKeys ? cleaned : undefined
  }
  return data
}

function getTemplateConfig(workspace) {
  const templateBlock = workspace?.getAllBlocks?.(false)
    .find(block => block.type === 'maa_template_config')
  if (!templateBlock) return null
  try {
    return JSON.parse(templateBlock.getFieldValue('TEMPLATE_JSON') || '{}')
  } catch {
    return null
  }
}

function getEnclosingProcedureName(block) {
  let parent = block?.getSurroundParent?.()
  while (parent) {
    if (parent.type === 'procedures_defnoreturn' || parent.type === 'procedures_defreturn') {
      return String(parent.getFieldValue('NAME') || '').trim()
    }
    parent = parent.getSurroundParent?.()
  }
  return ''
}

function getTemplateWorkflowContext(block) {
  const procedureName = getEnclosingProcedureName(block)
  const config = getTemplateConfig(block?.workspace)
  if (!procedureName || !config) return { procedureName, flows: [], parameterKeys: [] }

  const taskKeys = new Set((config.tasks || [])
    .filter(task => String(task?.fn || '').trim() === procedureName)
    .map(task => String(task?.k || '').trim())
    .filter(Boolean))
  const flows = (config.flows || []).filter(flow => (flow.steps || [])
    .some(step => taskKeys.has(String(step?.task || '').trim())))
  if (!flows.length) return { procedureName, flows, parameterKeys: [] }

  // A reused task may only address parameters exposed by every workflow that can invoke it.
  const commonKeys = new Set(Array.isArray(flows[0].g) ? flows[0].g : [])
  for (const flow of flows.slice(1)) {
    const flowKeys = new Set(Array.isArray(flow.g) ? flow.g : [])
    for (const key of commonKeys) {
      if (!flowKeys.has(key)) commonKeys.delete(key)
    }
  }
  return { procedureName, flows, parameterKeys: [...commonKeys] }
}

function getTemplateWorkflowDiagnostic(block, { requireParameter = false } = {}) {
  const context = getTemplateWorkflowContext(block)
  if (!context.procedureName) return '此块只能在模板任务函数内部使用。'
  if (!context.flows.length) return `函数 "${context.procedureName}" 未绑定到任何任务流。`
  if (requireParameter && !context.parameterKeys.length) return '关联任务流之间没有共同可用的任务流参数。'
  const selectedKey = String(block.getFieldValue?.('TPL_GLOBAL') || '').trim()
  if (requireParameter && selectedKey && !context.parameterKeys.includes(selectedKey)) {
    return `任务流参数 "${selectedKey}" 不适用于当前函数关联的全部任务流。`
  }
  if (requireParameter && !selectedKey) return '请选择任务流参数。'
  return null
}

function getTemplateWorkflowParameterItems(block) {
  const config = getTemplateConfig(block?.workspace) || {}
  const vars = config.vars || {}
  return getTemplateWorkflowContext(block).parameterKeys.map(key => ({
    label: vars[key]?.t ? `${vars[key].t} (${key})` : key,
    rawName: vars[key]?.t || key,
    value: key,
    desc: vars[key]?.note || '任务流参数',
  }))
}

function updateTemplateWorkflowBlock(block, { requireParameter = false } = {}) {
  if (!block?.workspace || block.isInFlyout || block.isDisposed?.()) return
  if (requireParameter) {
    const selectedKey = String(block.getFieldValue('TPL_GLOBAL') || '').trim()
    const selected = getTemplateWorkflowParameterItems(block).find(item => item.value === selectedKey)
    const nextLabel = selected?.rawName || selectedKey || '未选择'
    if (block.getFieldValue('TPL_GLOBAL_LABEL') !== nextLabel) {
      block.setFieldValue(nextLabel, 'TPL_GLOBAL_LABEL')
    }
  }
  block.setWarningText(getTemplateWorkflowDiagnostic(block, { requireParameter }))
}

function attachTemplateWorkflowWarning(block, options) {
  block.setOnChange((event) => {
    if (event && ![
      Blockly.Events.BLOCK_CREATE,
      Blockly.Events.BLOCK_CHANGE,
      Blockly.Events.BLOCK_MOVE,
      Blockly.Events.BLOCK_DELETE,
      Blockly.Events.FINISHED_LOADING,
    ].includes(event.type)) return
    updateTemplateWorkflowBlock(block, options)
  })
}

function attachTemplateWorkflowParameterPicker(block) {
  if (block.getIcon(PICKER_ICON_TYPE)) return
  const icon = new MaaPickerIcon(block, () => null)
  icon.onClick = () => {
    const items = getTemplateWorkflowParameterItems(block)
    actions.openBlocklyPicker({
      title: '选择任务流参数',
      summary: '仅显示当前函数关联任务流共同公开的参数。',
      items,
      currentValue: block.getFieldValue('TPL_GLOBAL') || null,
      emptyText: '当前函数没有可安全读写的任务流参数',
      onSelect: (selectedValue) => {
        if (!selectedValue) return
        const selected = items.find(item => item.value === selectedValue)
        block.setFieldValue(selectedValue, 'TPL_GLOBAL')
        block.setFieldValue(selected?.rawName || selectedValue, 'TPL_GLOBAL_LABEL')
        updateTemplateWorkflowBlock(block, { requireParameter: true })
      },
    })
  }
  block.addIcon(icon)
}

function initTemplateWorkflowParameterField(block) {
  block.appendDummyInput('PARAMETER')
    .appendField('任务流参数')
    .appendField('未选择', 'TPL_GLOBAL_LABEL')
  block.appendDummyInput('HIDDEN_PARAMETER')
    .appendField(new Blockly.FieldTextInput(''), 'TPL_GLOBAL')
    .setVisible(false)
  attachTemplateWorkflowParameterPicker(block)
  attachTemplateWorkflowWarning(block, { requireParameter: true })
}

export const templateBlocks = [
  {
    type: 'maa_template_config',
    category: '模板',
    colour: '#e67e22',
    definition: {
      message0: '%1 %2',
      args0: [
        {
          type: 'field_label',
          name: 'STATUS_LABEL',
          text: '任务流模板 未配置'
        },
        {
          type: 'field_input',
          name: 'TEMPLATE_JSON',
          text: '{}'
        }
      ],
      tooltip: '点击齿轮配置模板系统属性',
      helpUrl: '',
    },
    init(block) {
      const field = block.getField('TEMPLATE_JSON')
      if (field) field.setVisible(false)

      const labelField = block.getField('STATUS_LABEL')

      function updateLabel(jsonStr) {
        let isConfigured = false
        try {
          const parsed = JSON.parse(jsonStr)
          const cleanedData = cleanTemplateData(parsed) || {}
          if (Object.keys(cleanedData).length > 0) {
            isConfigured = true
          }
        } catch (e) {}
        if (labelField) {
          labelField.setValue(isConfigured ? '任务流模板 已配置' : '任务流模板 未配置')
        }
      }

      updateLabel(block.getFieldValue('TEMPLATE_JSON'))

      if (field) {
        field.setValidator(function(newValue) {
          updateLabel(newValue)
          return newValue
        })
      }

      if (!block.getIcon(PICKER_ICON_TYPE)) {
        const icon = new MaaPickerIcon(block, () => null)
        icon.onClick = () => {
          const currentJson = block.getFieldValue('TEMPLATE_JSON') || '{}'
          let parsed = {}
          try {
            parsed = JSON.parse(currentJson)
          } catch (e) {}
          
          state.templateEditorModalData.value = parsed
          state.templateEditorModalCallback.value = (newData) => {
            block.setFieldValue(JSON.stringify(newData), 'TEMPLATE_JSON')
          }
          state.templateEditorModalVisible.value = true
        }
        block.addIcon(icon)
      }
      attachBlockSemanticWarning(block)
    },
    generator(block) {
      const diagnostic = getBlockSemanticDiagnostic(block)
      if (diagnostic) throw new Error(diagnostic)
      const jsonStr = block.getFieldValue('TEMPLATE_JSON') || '{}'
      let jsonData = {}
      try {
        jsonData = JSON.parse(jsonStr)
      } catch (e) {
        console.error('Parse template JSON failed', e)
      }
      
      const cleanedData = cleanTemplateData(jsonData) || {}
      if (Object.keys(cleanedData).length === 0) {
        return '-- @mlua-template:start\n-- {}\n-- @mlua-template:end\n'
      }

      const formattedJson = JSON.stringify(cleanedData, null, 2)
      const lines = formattedJson.split('\n')
      const commentedLines = lines.map(line => `-- ${line}`)
      
      return [
        '-- @mlua-template:start',
        ...commentedLines,
        '-- @mlua-template:end',
        ''
      ].join('\n') + '\n'
    }
  },
  {
    type: 'template_state_get',
    category: '模板',
    colour: '#e67e22',
    init(block) {
      block.appendDummyInput()
        .appendField('模板运行状态')
        .appendField(new Blockly.FieldDropdown([
          ['任务流 Key', 'flowKey'],
          ['步骤 Key', 'stepKey'],
          ['任务 Key', 'taskKey'],
          ['步骤序号', 'stepIndex'],
          ['执行状态', 'status'],
        ]), 'STATE_FIELD')
      block.setOutput(true, null)
      block.setColour('#e67e22')
      block.setTooltip('读取引擎维护的当前模板运行状态。')
      attachTemplateWorkflowWarning(block)
    },
    generator(block) {
      const diagnostic = getTemplateWorkflowDiagnostic(block)
      if (diagnostic) throw new Error(diagnostic)
      const field = String(block.getFieldValue('STATE_FIELD') || 'status')
      return [`((shared.get_key("template_state") or {})[${JSON.stringify(field)}])`, luaOrder]
    },
  },
  {
    type: 'template_workflow_global_get',
    category: '模板',
    colour: '#e67e22',
    init(block) {
      initTemplateWorkflowParameterField(block)
      block.setOutput(true, null)
      block.setColour('#e67e22')
      block.setTooltip('读取当前任务流参数。')
    },
    generator(block) {
      const diagnostic = getTemplateWorkflowDiagnostic(block, { requireParameter: true })
      if (diagnostic) throw new Error(diagnostic)
      const key = String(block.getFieldValue('TPL_GLOBAL') || '').trim()
      return [`((shared.get_key("template_workflow_globals") or {})[${JSON.stringify(key)}])`, luaOrder]
    },
  },
  {
    type: 'template_workflow_global_set',
    category: '模板',
    colour: '#e67e22',
    init(block) {
      initTemplateWorkflowParameterField(block)
      block.appendValueInput('VALUE').appendField('设为')
      block.setPreviousStatement(true, null)
      block.setNextStatement(true, null)
      block.setColour('#e67e22')
      block.setTooltip('修改当前任务流参数，后续步骤分支会读取新值。')
    },
    generator(block, generator) {
      const diagnostic = getTemplateWorkflowDiagnostic(block, { requireParameter: true })
      if (diagnostic) throw new Error(diagnostic)
      const key = String(block.getFieldValue('TPL_GLOBAL') || '').trim()
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return [
        'do',
        '  local __mlua_template_globals = shared.get_key("template_workflow_globals") or {}',
        `  __mlua_template_globals[${JSON.stringify(key)}] = ${value}`,
        '  shared.set_key("template_workflow_globals", __mlua_template_globals)',
        'end',
        '',
      ].join('\n')
    },
  }
]
