import test from 'node:test'
import assert from 'node:assert/strict'
import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

import { getBlockSemanticDiagnostic } from '../src/blockly/blockSemanticDiagnostics.js'
import { getSelectableProjectModules, setProjectModuleRegistry } from '../src/features/projects/projectModuleRegistry.js'
import {
  createThreadTaskPickerConfig,
  generateThreadTask,
  generateThreadTaskId,
  getThreadTaskPickerItems,
  installThreadTaskSerialization,
  restoreThreadTaskSelection,
} from '../src/blockly/threadTaskSelection.js'

function registerTaskBlock() {
  Blockly.Blocks.thread_spawn_selected_function = {
    init() {
      this.jsonInit({
        type: 'thread_spawn_selected_function',
        message0: '作为任务运行 %1',
        args0: [{ type: 'field_label', name: 'TARGET_LABEL', text: '未选择函数' }],
        output: 'ThreadTask',
      })
      this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'TARGET_KIND').setVisible(false)
      this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'MODULE_VALUE').setVisible(false)
      this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'FUNCTION_VALUE').setVisible(false)
      this.appendDummyInput().appendField(new Blockly.FieldTextInput('[]'), 'PARAM_VALUES').setVisible(false)
      this.appendDummyInput().appendField(new Blockly.FieldTextInput('function'), 'CALL_STYLE').setVisible(false)
      installThreadTaskSerialization(this)
    },
  }
}

test('task picker keeps one selected function and its argument connections through XML', () => {
  registerTaskBlock()
  const workspace = new Blockly.Workspace()
  const block = workspace.newBlock('thread_spawn_selected_function')
  restoreThreadTaskSelection(block, {
    kind: 'module', moduleKey: 'lib/math', functionName: 'add', params: ['a', 'b'], callStyle: 'function',
  })
  const argument = workspace.newBlock('math_number')
  argument.setFieldValue('7', 'NUM')
  block.getInput('ARG_0').connection.connect(argument.outputConnection)

  const xml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace))
  const restoredWorkspace = new Blockly.Workspace()
  Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), restoredWorkspace)
  const restored = restoredWorkspace.getBlocksByType('thread_spawn_selected_function', false)[0]

  assert.match(xml, /<field name="MODULE_VALUE">lib\/math<\/field>/)
  assert.equal(restored.getFieldValue('TARGET_LABEL'), 'lib/math · add')
  assert.equal(restored.getFieldValue('FUNCTION_VALUE'), 'add')
  assert.equal(restored.getInput('ARG_0').connection.targetBlock().getFieldValue('NUM'), 7)
  assert.ok(restored.getInput('ARG_1'))

  restoreThreadTaskSelection(restored, { kind: 'local', functionName: 'work', params: ['value'] })
  assert.equal(restored.getInput('ARG_0').connection.targetBlock().getFieldValue('NUM'), 7)
  assert.equal(restored.getInput('ARG_1'), null)
})

test('task picker validates local and project function selections', () => {
  registerTaskBlock()
  setProjectModuleRegistry([{ key: 'lib/math', exports: [{ name: 'add', params: ['a', 'b'], callStyle: 'function' }] }])
  const workspace = new Blockly.Workspace()
  const localDefinition = workspace.newBlock('procedures_defnoreturn')
  localDefinition.setFieldValue('work', 'NAME')
  const block = workspace.newBlock('thread_spawn_selected_function')

  restoreThreadTaskSelection(block, { kind: 'local', functionName: 'work', params: [] })
  assert.equal(getBlockSemanticDiagnostic(block), '')
  restoreThreadTaskSelection(block, { kind: 'local', functionName: 'work', params: ['old'] })
  assert.match(getBlockSemanticDiagnostic(block), /参数已变化/)
  restoreThreadTaskSelection(block, { kind: 'module', moduleKey: 'lib/math', functionName: 'add', params: ['a', 'b'] })
  assert.equal(getBlockSemanticDiagnostic(block), '')
  const items = getThreadTaskPickerItems(workspace)
  assert.deepEqual(items.map(item => item.label), ['work', 'lib/math · add'])
  setProjectModuleRegistry([])
  assert.match(getBlockSemanticDiagnostic(block), /模块不存在/)
})

test('task menus exclude the current file and modules without explicit exports', () => {
  registerTaskBlock()
  setProjectModuleRegistry([
    { key: 'main', source: 'blockly/main.xml', kind: 'blockly', exports: [{ name: 'self', params: [] }] },
    { key: 'empty', source: 'blockly/empty.xml', kind: 'blockly', exports: [] },
    { key: 'other', source: 'blockly/other.xml', kind: 'blockly', exports: [{ name: 'work', params: ['value'] }] },
    { key: 'lib/tools', source: 'scripts/lib/tools.lua', kind: 'lua', exports: [{ name: 'run', params: [] }] },
  ])
  assert.deepEqual(getSelectableProjectModules('blockly/main.xml').map(item => item.key), ['other', 'lib/tools'])

  const workspace = new Blockly.Workspace()
  const localDefinition = workspace.newBlock('procedures_defnoreturn')
  localDefinition.setFieldValue('localWork', 'NAME')
  const block = workspace.newBlock('thread_spawn_selected_function')
  assert.deepEqual(
    getThreadTaskPickerItems(workspace, 'blockly/main.xml').map(item => item.functionName),
    ['localWork', 'work', 'run'],
  )

  const steps = []
  try {
    const root = createThreadTaskPickerConfig(block, 'blockly/main.xml', config => steps.push(config))
    assert.deepEqual(root.items.map(item => item.label), ['当前文件', '项目模块'])
    assert.equal(root.onSelect('local'), false)
    const localStep = steps.at(-1)
    assert.deepEqual(localStep.items.map(item => item.label), ['localWork'])
    assert.equal(localStep.onManage(), false)
    assert.equal(steps.at(-1).onManage, null)
    assert.equal(root.onSelect('module'), false)
    const moduleStep = steps.at(-1)
    assert.deepEqual(moduleStep.items.map(item => item.value), ['other', 'lib/tools'])
    assert.equal(moduleStep.onSelect('other'), false)
    const functionStep = steps.at(-1)
    assert.deepEqual(functionStep.items.map(item => item.label), ['work'])
    functionStep.onSelect(functionStep.items[0].value)
    assert.equal(block.getFieldValue('MODULE_VALUE'), 'other')
    assert.equal(block.getFieldValue('FUNCTION_VALUE'), 'work')
    assert.ok(block.getInput('ARG_0'))
  } finally {
    setProjectModuleRegistry([])
    workspace.dispose()
  }
})

test('one selected project function produces one task handle and passes arguments', () => {
  const block = {
    getFieldValue(name) {
      return { TARGET_KIND: 'module', MODULE_VALUE: 'lib/math', FUNCTION_VALUE: 'add', PARAM_VALUES: '["a","b"]', CALL_STYLE: 'function' }[name] || ''
    },
  }
  setProjectModuleRegistry([{ key: 'lib/math', exports: [{ name: 'add', params: ['a', 'b'], callStyle: 'function' }] }])
  const definitions = {}
  const code = generateThreadTask(block, {
    valueToCode(_block, name) { return { ARG_0: '7', ARG_1: '5' }[name] || '' },
    FUNCTION_NAME_PLACEHOLDER_: '{name}',
    provideFunction_(key, lines) { definitions[key] = lines.join('\n'); return '__project_task' },
  })[0]
  assert.equal(code, 'thread.spawn("__project_task", nil, "lib/math", "add", "function", 7, 5)')
  assert.match(Object.values(definitions)[0], /require\(moduleKey\)/)
  setProjectModuleRegistry([])
})

test('project task helper is emitted as a global Lua function for the child runtime', () => {
  setProjectModuleRegistry([{ key: 'lib/math', exports: [{ name: 'add', params: [], callStyle: 'function' }] }])
  const workspace = new Blockly.Workspace()
  luaGenerator.init(workspace)
  const generator = Object.create(luaGenerator)
  generator.valueToCode = () => ''
  const block = {
    getFieldValue(name) {
      return { TARGET_KIND: 'module', MODULE_VALUE: 'lib/math', FUNCTION_VALUE: 'add', PARAM_VALUES: '[]', CALL_STYLE: 'function' }[name] || ''
    },
  }
  const expression = generateThreadTask(block, generator)[0]
  const code = luaGenerator.finish(`local task = ${expression}`)
  assert.match(code, /function mlua_project_task\(moduleKey, functionName, callStyle, \.\.\.\)/)
  assert.match(code, /thread\.spawn\("mlua_project_task", nil, "lib\/math", "add", "function"\)/)
  setProjectModuleRegistry([])
})

test('task ID block reads the ID from a task handle', () => {
  assert.equal(generateThreadTaskId({}, { valueToCode() { return 'taskHandle' } })[0], '(taskHandle):id()')
})
