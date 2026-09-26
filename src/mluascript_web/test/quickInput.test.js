import assert from 'node:assert/strict'
import test from 'node:test'
import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

import {
  buildQuickInputShadows,
  QUICK_NUMBER_INPUT_BLOCK,
  QUICK_TEXT_INPUT_BLOCK,
  registerQuickInputBlocks,
} from '../src/blockly/quickInput.js'

test('typed scalar inputs receive blank replaceable shadows and explicit inputs win', () => {
  const inputs = buildQuickInputShadows({
    args0: [
      { type: 'input_value', name: 'COUNT', check: 'Number' },
      { type: 'input_value', name: 'NAME', check: 'String' },
      { type: 'input_value', name: 'IMAGE' },
      { type: 'input_value', name: 'ROI', check: 'MaaRoi' },
    ],
  }, {
    COUNT: { shadow: { type: 'custom_number' } },
  })

  assert.deepEqual(inputs, {
    COUNT: { shadow: { type: 'custom_number' } },
    NAME: { shadow: { type: QUICK_TEXT_INPUT_BLOCK } },
  })
})

test('blank quick inputs preserve parent fallback until the user enters a value', () => {
  registerQuickInputBlocks()
  Blockly.Blocks.quick_input_parent_probe = {
    init() {
      this.appendValueInput('NUMBER').setCheck('Number')
      this.appendValueInput('TEXT').setCheck('String')
      this.setOutput(true)
    },
  }
  luaGenerator.forBlock.quick_input_parent_probe = function(block, generator) {
    const number = generator.valueToCode(block, 'NUMBER', luaGenerator.ORDER_NONE) || '17'
    const text = generator.valueToCode(block, 'TEXT', luaGenerator.ORDER_NONE) || "'fallback'"
    return [`{${number}, ${text}}`, luaGenerator.ORDER_ATOMIC]
  }

  const workspace = new Blockly.Workspace()
  const parent = workspace.newBlock('quick_input_parent_probe')
  const number = workspace.newBlock(QUICK_NUMBER_INPUT_BLOCK)
  const text = workspace.newBlock(QUICK_TEXT_INPUT_BLOCK)
  assert.equal(number.inputList[0].fieldRow.length, 3)
  assert.equal(text.inputList[0].fieldRow.length, 3)
  number.setShadow(true)
  text.setShadow(true)
  parent.getInput('NUMBER').connection.connect(number.outputConnection)
  parent.getInput('TEXT').connection.connect(text.outputConnection)

  luaGenerator.init(workspace)
  assert.equal(luaGenerator.blockToCode(parent)[0], "{17, 'fallback'}")
  number.setFieldValue('12.5', 'VALUE')
  text.setFieldValue("it's ready", 'VALUE')
  assert.equal(luaGenerator.blockToCode(parent)[0], "{12.5, 'it\\'s ready'}")

  Blockly.Blocks.quick_input_number_source = {
    init() {
      this.setOutput(true, 'Number')
    },
  }
  luaGenerator.forBlock.quick_input_number_source = () => ['99', luaGenerator.ORDER_ATOMIC]
  const replacement = workspace.newBlock('quick_input_number_source')
  parent.getInput('NUMBER').connection.connect(replacement.outputConnection)
  assert.equal(parent.getInputTargetBlock('NUMBER'), replacement)
  assert.equal(luaGenerator.blockToCode(parent)[0], "{99, 'it\\'s ready'}")

  luaGenerator.finish('')
  workspace.dispose()
})
