import assert from 'node:assert/strict'
import test from 'node:test'
import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

import { loadBlocklyXml } from '../src/blockly/xmlImport.js'
import { replaceBlocklyWorkspace } from '../src/features/editor/blocklyWorkspace.js'

Blockly.Blocks.xml_import_statement = {
  init() {
    this.appendValueInput('VALUE').setCheck('Number')
    this.appendStatementInput('DO')
    this.setPreviousStatement(true)
    this.setNextStatement(true)
  },
}

function harness(t) {
  const workspace = new Blockly.Workspace()
  const messages = []
  const previousWindow = globalThis.window
  globalThis.window = { $message: { warning: message => messages.push(message) } }
  t.mock.method(console, 'warn', () => {})
  t.after(() => {
    workspace.dispose()
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  })
  return { workspace, messages }
}

test('valid XML retains fields, shadows and Lua generation without warnings', (t) => {
  const { workspace, messages } = harness(t)
  loadBlocklyXml(`<xml xmlns="https://developers.google.com/blockly/xml">
    <block type="text_print" id="print"><value name="TEXT">
      <shadow type="text"><field name="TEXT">正常内容</field></shadow>
    </value></block>
  </xml>`, workspace)
  assert.equal(workspace.getBlockById('print').getInputTargetBlock('TEXT').getFieldValue('TEXT'), '正常内容')
  assert.match(luaGenerator.workspaceToCode(workspace), /print\('正常内容'\)/)
  assert.deepEqual(messages, [])
})

test('unknown top block drops its input subtree and keeps the following stack and position', (t) => {
  const { workspace, messages } = harness(t)
  loadBlocklyXml(`<xml>
    <block type="maa_human_swipe" id="obsolete" x="120" y="80">
      <value name="X1"><block type="math_number" id="discarded"><field name="NUM">42</field></block></value>
      <next><block type="text_print" id="survivor"/></next>
    </block>
    <block type="text_print" id="independent"/>
  </xml>`, workspace)
  assert.equal(workspace.getBlockById('obsolete'), null)
  assert.equal(workspace.getBlockById('discarded'), null)
  assert.ok(workspace.getBlockById('independent'))
  const position = workspace.getBlockById('survivor').getRelativeToSurfaceXY()
  assert.equal(position.x, 120)
  assert.equal(position.y, 80)
  assert.match(messages[0], /maa_human_swipe × 1/)
  assert.match(messages[0], /已保留后续语句/)
})

test('consecutive unknown statements are removed and the previous and next statements reconnect', (t) => {
  const { workspace, messages } = harness(t)
  loadBlocklyXml(`<xml><block type="text_print" id="first"><next>
    <block type="removed_a"><next><block type="removed_b"><next>
      <block type="text_print" id="last"/>
    </next></block></next></block>
  </next></block></xml>`, workspace)
  assert.equal(workspace.getBlockById('first').getNextBlock(), workspace.getBlockById('last'))
  assert.equal(workspace.getAllBlocks(false).length, 2)
  assert.equal(messages.length, 1)
  assert.match(messages[0], /已删除 2 个/)
  assert.match(messages[0], /removed_a × 1、removed_b × 1/)
})

test('unknown statement inputs retain their continuation while unknown values and shadows are dropped', (t) => {
  const { workspace } = harness(t)
  loadBlocklyXml(`<xml><block type="xml_import_statement" id="parent">
    <value name="VALUE"><shadow type="removed_shadow"/><block type="removed_value"/></value>
    <statement name="DO"><block type="removed_statement">
      <statement name="DO"><block type="text_print" id="discarded"/></statement>
      <next><block type="text_print" id="retained"/></next>
    </block></statement>
  </block></xml>`, workspace)
  const parent = workspace.getBlockById('parent')
  assert.equal(parent.getInputTargetBlock('VALUE'), null)
  assert.equal(parent.getInputTargetBlock('DO'), workspace.getBlockById('retained'))
  assert.equal(workspace.getBlockById('discarded'), null)
})

test('known shadow remains usable when its unknown overriding value is removed', (t) => {
  const { workspace } = harness(t)
  loadBlocklyXml(`<xml><block type="xml_import_statement" id="parent"><value name="VALUE">
    <shadow type="math_number"><field name="NUM">7</field></shadow>
    <block type="removed_value"/>
  </value></block></xml>`, workspace)
  assert.equal(workspace.getBlockById('parent').getInputTargetBlock('VALUE').getFieldValue('NUM'), 7)
})

test('all-unknown XML becomes an empty workspace and reports unknown types inside discarded inputs', (t) => {
  const { workspace, messages } = harness(t)
  loadBlocklyXml(`<xml><block type="removed_a"><value name="VALUE">
    <block type="removed_a"><next><block type="removed_b"/></next></block>
  </value><next><block type="constructor"><next><block/></next></block></next></block></xml>`, workspace)
  assert.equal(workspace.getAllBlocks(false).length, 0)
  assert.match(messages[0], /已删除 5 个/)
  assert.match(messages[0], /removed_a × 2/)
  assert.match(messages[0], /removed_b × 1/)
  assert.match(messages[0], /constructor × 1/)
  assert.match(messages[0], /缺少 type × 1/)
})

test('replacing an open workspace uses the same tolerant loader and restores Blockly events', async (t) => {
  const { workspace, messages } = harness(t)
  workspace.newBlock('text_print', 'previous')
  await replaceBlocklyWorkspace(workspace, '<xml><block type="old_type"><next><block type="text_print" id="next"/></next></block></xml>')
  assert.equal(workspace.getBlockById('previous'), null)
  assert.ok(workspace.getBlockById('next'))
  assert.equal(Blockly.Events.isEnabled(), true)
  assert.equal(messages.length, 1)
})

test('invalid XML remains an explicit error', (t) => {
  const { workspace, messages } = harness(t)
  assert.throws(() => loadBlocklyXml('not XML', workspace))
  assert.deepEqual(messages, [])
})
