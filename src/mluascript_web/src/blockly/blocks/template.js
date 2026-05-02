import * as Blockly from 'blockly'
import { PICKER_ICON_TYPE } from '../constants'
import { MaaPickerIcon } from '../fields'
import { state } from '../../store'

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
    },
    generator(block) {
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
  }
]
