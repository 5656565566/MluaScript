import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

export const QUICK_NUMBER_INPUT_BLOCK = 'lua_quick_number_input'
export const QUICK_TEXT_INPUT_BLOCK = 'lua_quick_text_input'

const quickBlockTypesByCheck = {
  Number: QUICK_NUMBER_INPUT_BLOCK,
  String: QUICK_TEXT_INPUT_BLOCK,
}

const numberPattern = /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/

export function buildQuickInputShadows(definition = {}, explicitInputs = {}) {
  const inputs = {}
  for (const [key, args] of Object.entries(definition)) {
    if (!/^args\d+$/.test(key) || !Array.isArray(args)) continue
    for (const arg of args) {
      const shadowType = arg?.type === 'input_value' ? quickBlockTypesByCheck[arg.check] : null
      if (!shadowType || !arg.name) continue
      inputs[arg.name] = { shadow: { type: shadowType } }
    }
  }
  return { ...inputs, ...explicitInputs }
}

export function registerQuickInputBlocks() {
  Blockly.Blocks[QUICK_NUMBER_INPUT_BLOCK] = {
    init() {
      this.appendDummyInput()
        .appendField('\u00A0')
        .appendField(new Blockly.FieldTextInput('', (value) => {
          const text = String(value ?? '').trim()
          return text === '' || numberPattern.test(text) ? text : null
        }), 'VALUE')
        .appendField('\u00A0')
      this.setOutput(true, 'Number')
      this.setStyle('math_blocks')
      this.setTooltip('直接输入数字；留空时保持父积木原有默认行为')
      this.setHelpUrl('')
    },
  }
  luaGenerator.forBlock[QUICK_NUMBER_INPUT_BLOCK] = function(block) {
    const value = String(block.getFieldValue('VALUE') ?? '').trim()
    return [numberPattern.test(value) ? value : '', luaGenerator.ORDER_ATOMIC]
  }

  Blockly.Blocks[QUICK_TEXT_INPUT_BLOCK] = {
    init() {
      this.appendDummyInput()
        .appendField('\u00A0')
        .appendField(new Blockly.FieldTextInput(''), 'VALUE')
        .appendField('\u00A0')
      this.setOutput(true, 'String')
      this.setStyle('text_blocks')
      this.setTooltip('直接输入文本；留空时保持父积木原有默认行为')
      this.setHelpUrl('')
    },
  }
  luaGenerator.forBlock[QUICK_TEXT_INPUT_BLOCK] = function(block, generator) {
    const value = String(block.getFieldValue('VALUE') ?? '')
    return [value === '' ? '' : generator.quote_(value), luaGenerator.ORDER_ATOMIC]
  }
}
