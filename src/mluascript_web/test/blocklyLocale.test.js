import assert from 'node:assert/strict'
import test from 'node:test'

import { applyBlocklyZhCnLocale } from '../src/blockly/locale.js'

test('Blockly 复制和剪切提示使用简体中文', () => {
  const locale = { TEST_MESSAGE: '测试' }
  const Blockly = {
    Msg: {},
    setLocale(value) {
      Object.assign(this.Msg, value)
    },
  }

  applyBlocklyZhCnLocale(Blockly, locale)

  assert.equal(Blockly.Msg.TEST_MESSAGE, '测试')
  assert.equal(Blockly.Msg.KEYBOARD_NAV_COPIED_HINT, '已复制。按下 %1 粘贴。')
  assert.equal(Blockly.Msg.KEYBOARD_NAV_CUT_HINT, '已剪切。按下 %1 粘贴。')
  assert.doesNotMatch(Blockly.Msg.KEYBOARD_NAV_COPIED_HINT, /拷貝|貼上|剪下/)
  assert.doesNotMatch(Blockly.Msg.KEYBOARD_NAV_CUT_HINT, /拷貝|貼上|剪下/)
})
