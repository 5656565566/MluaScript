import test from 'node:test'
import assert from 'node:assert/strict'
import * as Blockly from 'blockly'

import {
  applyProjectModuleFunctionSelection,
  getProjectModuleCallBlockType,
  installProjectModuleCallSerialization,
  migrateLegacyProjectModuleCallXml,
  restoreProjectModuleCallState,
} from '../src/blockly/projectModuleCall.js'

function registerSerializableProjectCallBlocks() {
  for (const type of ['lua_project_module_call_stmt', 'lua_project_module_call_expr']) {
    Blockly.Blocks[type] = {
      init() {
        this.jsonInit({
          type,
          message0: '调用 %1',
          args0: [{ type: 'field_label', name: 'CALL_LABEL', text: '未选择' }],
          ...(type.endsWith('_expr')
            ? { output: null }
            : { previousStatement: null, nextStatement: null }),
        })
        this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'MODULE_VALUE').setVisible(false)
        this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'FUNCTION_VALUE').setVisible(false)
        this.appendDummyInput().appendField(new Blockly.FieldTextInput('[]'), 'PARAM_VALUES').setVisible(false)
        this.appendDummyInput().appendField(new Blockly.FieldTextInput('function'), 'CALL_STYLE').setVisible(false)
        installProjectModuleCallSerialization(this)
      },
    }
  }
}

function createConnection() {
  return {
    connectedTo: null,
    disconnectCount: 0,
    disconnect() { this.disconnectCount += 1 },
    connect(other) { this.connectedTo = other },
    isConnected() { return Boolean(this.connectedTo) },
  }
}

function createBlock(type, workspace, { previousTarget = null, nextTarget = null, outputTarget = null, argTarget = null } = {}) {
  const fields = {}
  const inputs = argTarget ? [{ name: 'ARG_0', connection: { targetConnection: argTarget } }] : []
  return {
    type,
    workspace,
    inputList: inputs,
    fields,
    previousConnection: previousTarget ? { targetConnection: previousTarget } : null,
    nextConnection: nextTarget ? { targetConnection: nextTarget } : null,
    outputConnection: outputTarget ? { targetConnection: outputTarget } : null,
    setFieldValue(value, name) { fields[name] = value },
    removeInput(name) {
      const index = this.inputList.findIndex(input => input.name === name)
      if (index >= 0) this.inputList.splice(index, 1)
    },
    appendValueInput(name) {
      const input = { name, connection: createConnection() }
      this.inputList.push(input)
      return { appendField() { return this } }
    },
    getInput(name) { return this.inputList.find(input => input.name === name) || null },
    getRelativeToSurfaceXY() { return { x: 12, y: 34 } },
    moveBy(x, y) { this.position = { x, y } },
    dispose(healStack) { this.disposedWith = healStack },
    isDisposed() { return false },
    select() { this.selected = true },
  }
}

function createWorkspace(targetType) {
  const workspace = {
    newBlock(type) {
      assert.equal(type, targetType)
      const block = createBlock(type, workspace)
      if (type.endsWith('_expr')) block.outputConnection = createConnection()
      else {
        block.previousConnection = createConnection()
        block.nextConnection = createConnection()
      }
      workspace.created = block
      return block
    },
  }
  return workspace
}

test('project module function return shape chooses the matching call block', () => {
  assert.equal(getProjectModuleCallBlockType('lua_project_module_call_stmt', true), 'lua_project_module_call_expr')
  assert.equal(getProjectModuleCallBlockType('lua_project_module_call_expr', false), 'lua_project_module_call_stmt')
  assert.equal(getProjectModuleCallBlockType('lua_project_module_call_stmt', null), 'lua_project_module_call_stmt')
})

test('selecting a value function replaces a statement call and preserves its argument and statement chain', () => {
  const previousTarget = createConnection()
  const nextTarget = createConnection()
  const argTarget = createConnection()
  const workspace = createWorkspace('lua_project_module_call_expr')
  const oldBlock = createBlock('lua_project_module_call_stmt', workspace, { previousTarget, nextTarget, argTarget })

  const newBlock = applyProjectModuleFunctionSelection(oldBlock, 'lib/math', {
    name: 'add',
    params: ['a', 'b'],
    hasReturn: true,
    callStyle: 'function',
  })

  assert.equal(newBlock.type, 'lua_project_module_call_expr')
  assert.equal(newBlock.fields.MODULE_VALUE, 'lib/math')
  assert.equal(newBlock.fields.FUNCTION_VALUE, 'add')
  assert.equal(newBlock.fields.PARAM_VALUES, '["a","b"]')
  assert.equal(newBlock.fields.CALL_LABEL, 'lib/math · add')
  assert.equal(newBlock.inputList.length, 2)
  assert.equal(newBlock.getInput('ARG_0').connection.connectedTo, argTarget)
  assert.equal(previousTarget.connectedTo, nextTarget)
  assert.equal(oldBlock.disposedWith, false)
})

test('selecting a procedure function replaces a value call and records method syntax', () => {
  const outputTarget = createConnection()
  const workspace = createWorkspace('lua_project_module_call_stmt')
  const oldBlock = createBlock('lua_project_module_call_expr', workspace, { outputTarget })

  const newBlock = applyProjectModuleFunctionSelection(oldBlock, 'lib/session', {
    name: 'reset',
    params: [],
    hasReturn: false,
    callStyle: 'method',
  })

  assert.equal(newBlock.type, 'lua_project_module_call_stmt')
  assert.equal(newBlock.fields.CALL_STYLE, 'method')
  assert.equal(outputTarget.disconnectCount, 1)
  assert.equal(oldBlock.disposedWith, false)
})

test('project module calls preserve their selection and connected arguments through XML', () => {
  registerSerializableProjectCallBlocks()
  const workspace = new Blockly.Workspace()
  const block = workspace.newBlock('lua_project_module_call_expr')
  restoreProjectModuleCallState(block, {
    moduleKey: 'lib/math',
    functionName: 'add',
    params: ['a', 'b'],
    callStyle: 'function',
  })
  const argument = workspace.newBlock('math_number')
  argument.setFieldValue('7', 'NUM')
  block.getInput('ARG_0').connection.connect(argument.outputConnection)

  const xml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace))
  const restoredWorkspace = new Blockly.Workspace()
  Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), restoredWorkspace)
  const restored = restoredWorkspace.getBlocksByType('lua_project_module_call_expr', false)[0]

  assert.match(xml, /<mutation module="lib\/math" function="add"/)
  assert.equal(restored.getFieldValue('CALL_LABEL'), 'lib/math · add')
  assert.equal(restored.getFieldValue('PARAM_VALUES'), '["a","b"]')
  assert.equal(restored.getInput('ARG_0').connection.targetBlock().getFieldValue('NUM'), 7)
  assert.ok(restored.getInput('ARG_1'))
})

test('legacy project module call XML is upgraded before Blockly reconnects argument blocks', () => {
  registerSerializableProjectCallBlocks()
  const legacyXml = Blockly.utils.xml.textToDom(`<xml xmlns="https://developers.google.com/blockly/xml">
    <block type="lua_project_module_call_expr">
      <field name="MODULE_VALUE">lib/math</field>
      <field name="FUNCTION_VALUE">add</field>
      <field name="PARAM_VALUES">["a","b"]</field>
      <field name="CALL_STYLE">function</field>
      <value name="ARG_0"><block type="math_number"><field name="NUM">9</field></block></value>
    </block>
  </xml>`)

  migrateLegacyProjectModuleCallXml(legacyXml)
  const workspace = new Blockly.Workspace()
  Blockly.Xml.domToWorkspace(legacyXml, workspace)
  const restored = workspace.getBlocksByType('lua_project_module_call_expr', false)[0]

  assert.equal(restored.getFieldValue('CALL_LABEL'), 'lib/math · add')
  assert.equal(restored.getInput('ARG_0').connection.targetBlock().getFieldValue('NUM'), 9)
  assert.ok(restored.getInput('ARG_1'))
})
