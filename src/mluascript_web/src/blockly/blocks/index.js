import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'
import { templateBlocks } from './template'
import { deviceBlocks } from './device'
import { visionBlocks } from './vision'
import { luaCoreBlocks } from './lua_core'
import { luaTableBlocks } from './lua_table'
import { luaStringBlocks } from './lua_string'
import { luaThreadBlocks } from './lua_thread'
import { luaCoroutineBlocks } from './lua_coroutine'
import { functionBlocks } from './function'
import { getProcedurePickerItems, getProcedureDefinitionByName, applyProcedureSelectionToPickerBlock } from '../utils'
import { MaaPickerIcon, LuaVariableField } from '../fields'
import { PICKER_ICON_TYPE } from '../constants'

const unsupportedDeviceBlockTypes = new Set([
  'maa_human_swipe',
  'maa_human_swipe_preset_steady',
  'maa_human_swipe_preset_natural',
  'maa_human_swipe_preset_drag_precise',
  'maa_human_swipe_preset_scroll_vertical',
])


export const dynamicBlockSpecs = [
  ...templateBlocks,
  ...deviceBlocks.filter((block) => !unsupportedDeviceBlockTypes.has(block.type)),
  ...visionBlocks,
  ...luaCoreBlocks,
  ...luaTableBlocks,
  ...luaStringBlocks,
  ...luaThreadBlocks,
  ...luaCoroutineBlocks,
  ...functionBlocks,
]

function initCustomVariableField(block, config) {
  const firstInput = block.inputList?.[0]
  if (!firstInput) return
  firstInput.appendField(new LuaVariableField(null, config), 'VAR')
}

let registered = false

export function ensureBlocklyBlocks() {
  if (registered) return

  const patchProcedureCallBlock = (blockType) => {
    const originalInit = Blockly.Blocks[blockType]?.init
    if (!originalInit) return
    Blockly.Blocks[blockType].init = function() {
      originalInit.call(this)
      if (!this.getIcon(PICKER_ICON_TYPE)) {
        this.addIcon(new MaaPickerIcon(this, () => ({
          title: '重新选择函数',
          items: getProcedurePickerItems(this.workspace),
          currentValue: this.getFieldValue('NAME') || null,
          emptyText: '请先定义函数后再调用',
          onSelect: (selectedValue) => {
            if (!selectedValue) return
            const updated = applyProcedureSelectionToPickerBlock(this, selectedValue)
            if (!updated) {
              this.setWarningText('未找到对应函数定义，请重新选择')
            }
          },
        })))
      }
    }
  }

  patchProcedureCallBlock('procedures_callnoreturn')
  patchProcedureCallBlock('procedures_callreturn')

  Blockly.Blocks.procedure_call_picker = {
    init() {
      this.appendDummyInput('TOPROW')
        .appendField('调用函数')
        .appendField('未选择函数', 'SELECTED_LABEL')
      this.setPreviousStatement(true)
      this.setNextStatement(true)
      this.setStyle('procedure_blocks')
      this.setTooltip('拖出后点击齿轮选择函数，将替换为原生函数调用块。')
      this.setHelpUrl('')
      this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput(''), 'PROC_NAME')
        .setVisible(false)
      if (!this.getIcon(PICKER_ICON_TYPE)) {
        this.addIcon(new MaaPickerIcon(this, () => ({
          title: '选择函数',
          items: getProcedurePickerItems(this.workspace),
          currentValue: this.getFieldValue('PROC_NAME') || null,
          emptyText: '请先定义函数后再调用',
          onSelect: (selectedValue) => {
            if (!selectedValue) return
            const updated = applyProcedureSelectionToPickerBlock(this, selectedValue)
            if (!updated) {
              this.setWarningText('未找到对应函数定义，请重新选择')
            }
          },
        })))
      }
      this.setOnChange(() => {
        if (!this.workspace || this.isInFlyout || this.isDisposed?.()) return
        const selectedName = this.getFieldValue('PROC_NAME') || ''
        if (!selectedName) {
          this.setFieldValue('未选择函数', 'SELECTED_LABEL')
          this.setWarningText('请点击齿轮选择函数')
          return
        }
        const definition = getProcedureDefinitionByName(selectedName, this.workspace)
        if (!definition) {
          this.setWarningText('当前选择的函数不存在，请重新选择')
          return
        }
        this.setFieldValue(selectedName, 'SELECTED_LABEL')
        this.setWarningText(null)
      })
    },
  }
  luaGenerator.forBlock.procedure_call_picker = function() {
    return '-- 请先选择函数，块会自动替换为原生调用块\n'
  }

  Blockly.Blocks.variables_get = {
    init() {
      this.appendDummyInput()
      initCustomVariableField(this, {
        fieldName: 'VAR',
        includeGlobals: true,
        includeLocals: true,
        includeArguments: false,
        includeRename: true,
        includeDelete: true,
        title: '选择变量',
        emptyText: '当前范围内没有可选变量',
        defaultLabel: '选择变量…',
      })
      this.setOutput(true, null)
      this.setStyle('variable_blocks')
      this.setTooltip(Blockly.Msg.VARIABLES_GET_TOOLTIP || '')
      this.setHelpUrl(Blockly.Msg.VARIABLES_GET_HELPURL || '')
    },
  }

  Blockly.Blocks.variables_set = {
    init() {
      this.appendValueInput('VALUE')
        .appendField('赋值')
      initCustomVariableField(this, {
        fieldName: 'VAR',
        includeGlobals: true,
        includeLocals: true,
        includeArguments: false,
        includeRename: true,
        includeDelete: true,
        title: '选择变量',
        emptyText: '当前范围内没有可选变量',
        defaultLabel: '选择变量…',
      })
      this.getInput('VALUE')?.appendField('为')
      this.setPreviousStatement(true, null)
      this.setNextStatement(true, null)
      this.setStyle('variable_blocks')
      this.setTooltip(Blockly.Msg.VARIABLES_SET_TOOLTIP || '')
      this.setHelpUrl(Blockly.Msg.VARIABLES_SET_HELPURL || '')
    },
  }

  Blockly.Blocks.math_change = {
    init() {
      this.appendValueInput('DELTA')
        .setCheck('Number')
        .appendField('给')
      initCustomVariableField(this, {
        fieldName: 'VAR',
        includeGlobals: true,
        includeLocals: true,
        includeArguments: false,
        includeRename: true,
        includeDelete: true,
        title: '选择变量',
        emptyText: '当前范围内没有可选变量',
        defaultLabel: '选择变量…',
      })
      this.getInput('DELTA')?.appendField('加')
      this.setPreviousStatement(true, null)
      this.setNextStatement(true, null)
      this.setStyle('variable_blocks')
      this.setTooltip(Blockly.Msg.MATH_CHANGE_TOOLTIP || '')
      this.setHelpUrl(Blockly.Msg.MATH_CHANGE_HELPURL || '')
    },
  }

  Blockly.Blocks.math_number = {
    init() {
      this.appendDummyInput()
        .appendField('\u00A0')
        .appendField(new Blockly.FieldTextInput('0', (value) => {
          const text = String(value ?? '').trim()
          return /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text) ? text : null
        }), 'NUM')
        .appendField('\u00A0')
      this.setOutput(true, 'Number')
      this.setStyle('math_blocks')
      this.setColour('#5b67a5')
      this.setTooltip(Blockly.Msg.MATH_NUMBER_TOOLTIP || '')
      this.setHelpUrl(Blockly.Msg.MATH_NUMBER_HELPURL || '')
    },
  }

  luaGenerator.forBlock.math_number = function(block) {
    const rawCode = String(block.getFieldValue('NUM') ?? '0').trim()
    const code = /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(rawCode) ? rawCode : '0'
    return [code, luaGenerator.ORDER_ATOMIC]
  }

  for (const spec of dynamicBlockSpecs) {
    if (spec.type === 'procedure_call_picker') {
      luaGenerator.forBlock[spec.type] = spec.generator
      continue
    }
    Blockly.Blocks[spec.type] = {
      init() {
        const jsonDef = { type: spec.type, ...spec.definition }
        if (spec.colour !== undefined) {
          jsonDef.colour = spec.colour
        }
        if (Object.keys(jsonDef).length > 1) {
          this.jsonInit(jsonDef)
        }
        if (typeof spec.init === 'function') {
          spec.init(this)
        }
      },
    }
    luaGenerator.forBlock[spec.type] = spec.generator
  }

  registered = true
}
