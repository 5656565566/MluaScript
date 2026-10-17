import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

import { luaReflectionBlocks } from '../src/blockly/blocks/lua_reflection.js'
import { buildQuickInputShadows, registerQuickInputBlocks } from '../src/blockly/quickInput.js'

registerQuickInputBlocks()

for (const spec of luaReflectionBlocks) {
  Blockly.Blocks[spec.type] = {
    init() { this.jsonInit({ type: spec.type, colour: spec.colour, ...spec.definition }) },
  }
  luaGenerator.forBlock[spec.type] = spec.generator
}

Blockly.Blocks.reflection_test_value = {
  init() {
    this.appendDummyInput().appendField(new Blockly.FieldTextInput('nil'), 'CODE')
    this.setOutput(true)
  },
}
luaGenerator.forBlock.reflection_test_value = block => [block.getFieldValue('CODE'), luaGenerator.ORDER_ATOMIC]
Blockly.Blocks.reflection_test_statement = {
  init() {
    this.appendValueInput('VALUE').appendField(new Blockly.FieldTextInput('return %s'), 'CODE')
    this.setPreviousStatement(true)
    this.setNextStatement(true)
  },
}
luaGenerator.forBlock.reflection_test_statement = (block, generator) =>
  block.getFieldValue('CODE').replace('%s', generator.valueToCode(block, 'VALUE', generator.ORDER_NONE) || 'nil') + '\n'
Blockly.Blocks.reflection_test_run_task = {
  init() {
    this.appendDummyInput().appendField(new Blockly.FieldTextInput('worker'), 'NAME')
    this.setOutput(true)
  },
}
luaGenerator.forBlock.reflection_test_run_task = (block, generator) => [
  `(function() local task = thread.spawn(${generator.quote_(generator.getProcedureName(block.getFieldValue('NAME')))}) `
    + 'assert(task:join(2)); assert(not task:error() or task:error() == "", task:error()); return task:result() end)()',
  generator.ORDER_ATOMIC,
]

function value(workspace, code) {
  const block = workspace.newBlock('reflection_test_value')
  block.setFieldValue(code, 'CODE')
  return block
}

function statement(workspace, code, input = null) {
  const block = workspace.newBlock('reflection_test_statement')
  block.setFieldValue(code, 'CODE')
  if (input) block.getInput('VALUE').connection.connect(input.outputConnection)
  return block
}

function chain(...blocks) {
  blocks.slice(1).forEach((block, index) => blocks[index].nextConnection.connect(block.previousConnection))
}

function lookup(workspace, type, name, mode = 'BLOCKLY') {
  const block = workspace.newBlock(type)
  if (block.getField('NAME_MODE')) block.setFieldValue(mode, 'NAME_MODE')
  block.getInput('NAME').connection.connect(value(workspace, name).outputConnection)
  return block
}

function call(workspace, target, args = null, type = 'reflection_call_return') {
  const block = workspace.newBlock(type)
  block.getInput('FUNCTION').connection.connect(target.outputConnection)
  if (args !== null) block.getInput('ARGS').connection.connect(value(workspace, args).outputConnection)
  return block
}

function assign(workspace, name, code) {
  const model = workspace.getVariableMap().createVariable(name)
  const block = workspace.newBlock('variables_set')
  block.setFieldValue(model.getId(), 'VAR')
  block.getInput('VALUE').connection.connect((typeof code === 'string' ? value(workspace, code) : code).outputConnection)
  return block
}

function define(workspace, name, result) {
  const block = workspace.newBlock('procedures_defreturn')
  block.setFieldValue(name, 'NAME')
  block.getInput('RETURN').connection.connect(result.outputConnection)
  return block
}

function generate(build) {
  const workspace = new Blockly.Workspace()
  try {
    build(workspace)
    return luaGenerator.workspaceToCode(workspace)
  } finally {
    workspace.dispose()
  }
}

test('reflection exposes five serializable blocks with replaceable string inputs', () => {
  assert.equal(luaReflectionBlocks.length, 5)
  assert.ok(luaReflectionBlocks.every(spec => spec.category === '反射'))
  const workspace = new Blockly.Workspace()
  const restoredWorkspace = new Blockly.Workspace()
  try {
    for (const spec of luaReflectionBlocks) workspace.newBlock(spec.type)
    const global = workspace.getBlocksByType('reflection_get_global', false)[0]
    assert.equal(global.getFieldValue('NAME_MODE'), 'BLOCKLY')
    global.setFieldValue('RAW', 'NAME_MODE')
    const target = workspace.getBlocksByType('reflection_get_function', false)[0]
    target.getInput('NAME').connection.connect(value(workspace, "'执行任务'").outputConnection)
    const invocation = workspace.getBlocksByType('reflection_call_return', false)[0]
    invocation.getInput('FUNCTION').connection.connect(target.outputConnection)
    invocation.getInput('ARGS').connection.connect(value(workspace, 'table.pack(nil, false, nil)').outputConnection)

    const xml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace))
    Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), restoredWorkspace)
    const restored = restoredWorkspace.getBlocksByType('reflection_call_return', false)[0]
    assert.equal(restored.getInputTargetBlock('FUNCTION').getInputTargetBlock('NAME').getFieldValue('CODE'), "'执行任务'")
    assert.equal(restored.getInputTargetBlock('ARGS').getFieldValue('CODE'), 'table.pack(nil, false, nil)')
    assert.equal(restoredWorkspace.getBlocksByType('reflection_get_global', false)[0].getFieldValue('NAME_MODE'), 'RAW')
    assert.equal(restoredWorkspace.getBlocksByType('reflection_call', false)[0].outputConnection, null)
    assert.equal(buildQuickInputShadows(luaReflectionBlocks[0].definition).NAME.shadow.type, 'lua_quick_text_input')
  } finally {
    workspace.dispose()
    restoredWorkspace.dispose()
  }
})

test('call defaults are non-draggable shadows that restore after variable overrides', () => {
  for (const spec of luaReflectionBlocks.filter(spec => spec.toolboxInputs)) {
    const workspace = new Blockly.Workspace()
    const restoredWorkspace = new Blockly.Workspace()
    try {
      const invocation = Blockly.serialization.blocks.append({
        type: spec.type,
        inputs: buildQuickInputShadows(spec.definition, spec.toolboxInputs),
      }, workspace)
      const target = invocation.getInputTargetBlock('FUNCTION')
      assert.equal(invocation.getInput('FUNCTION').connection.getCheck(), null)
      assert.equal(target.type, 'reflection_get_function')
      assert.equal(target.getFieldValue('NAME_MODE'), 'BLOCKLY')
      assert.equal(target.isShadow(), true)
      assert.equal(target.isMovable(), false)
      const name = target.getInputTargetBlock('NAME')
      assert.equal(name.isShadow(), true)
      name.setFieldValue('执行任务', 'VALUE')

      const defaultXml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace))
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(defaultXml), restoredWorkspace)
      const restoredTarget = restoredWorkspace.getBlocksByType(spec.type, false)[0].getInputTargetBlock('FUNCTION')
      assert.equal(restoredTarget.isShadow(), true)
      assert.equal(restoredTarget.isMovable(), false)
      assert.equal(restoredTarget.getInputTargetBlock('NAME').getFieldValue('VALUE'), '执行任务')

      const computedTarget = lookup(workspace, 'reflection_get_function', "'执行' .. '任务'")
      invocation.getInput('FUNCTION').connection.connect(computedTarget.outputConnection)
      assert.equal(invocation.getInputTargetBlock('FUNCTION'), computedTarget)
      assert.equal(target.isDisposed(), true)
      computedTarget.outputConnection.disconnect()
      computedTarget.dispose()
      assert.equal(invocation.getInputTargetBlock('FUNCTION').isShadow(), true)
      assert.equal(invocation.getInputTargetBlock('FUNCTION').getInputTargetBlock('NAME').getFieldValue('VALUE'), '执行任务')
      const model = workspace.getVariableMap().createVariable('函数引用')
      const variable = workspace.newBlock('variables_get')
      variable.setFieldValue(model.getId(), 'VAR')
      invocation.getInput('FUNCTION').connection.connect(variable.outputConnection)
      assert.equal(invocation.getInputTargetBlock('FUNCTION'), variable)
      assert.equal(workspace.getBlocksByType('reflection_get_function', false).length, 0)

      const xml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace))
      restoredWorkspace.clear()
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), restoredWorkspace)
      const restoredInvocation = restoredWorkspace.getBlocksByType(spec.type, false)[0]
      const restoredVariable = restoredInvocation.getInputTargetBlock('FUNCTION')
      assert.equal(restoredVariable.type, 'variables_get')
      restoredVariable.outputConnection.disconnect()
      const restoredDefault = restoredInvocation.getInputTargetBlock('FUNCTION')
      assert.equal(restoredDefault.isShadow(), true)
      assert.equal(restoredDefault.isMovable(), false)
      assert.equal(restoredDefault.getInputTargetBlock('NAME').getFieldValue('VALUE'), '执行任务')
    } finally {
      workspace.dispose()
      restoredWorkspace.dispose()
    }
  }
})

test('name mappings use final Blockly names and exclude procedure arguments', () => {
  const workspace = new Blockly.Workspace()
  try {
    const names = ['计数', 'a-b', 'a b', 'end', '1abc', 'mlua_reflection_name']
    names.forEach((name, index) => assign(workspace, name, String(index)))
    const procedure = define(workspace, '计数', value(workspace, '42'))
    procedure.domToMutation(Blockly.utils.xml.textToDom('<mutation><arg name="仅参数"></arg></mutation>'))
    const variable = lookup(workspace, 'reflection_get_global', "'计数'")
    const fn = lookup(workspace, 'reflection_get_function', "'计数'")
    luaGenerator.init(workspace)
    luaGenerator.blockToCode(variable)
    luaGenerator.blockToCode(fn)
    const variableDefinition = luaGenerator.definitions_.mlua_reflection_variable
    const functionDefinition = luaGenerator.definitions_.mlua_reflection_function
    for (const model of workspace.getVariableMap().getVariablesOfType('')) {
      if (model.name === '仅参数') continue
      assert.ok(variableDefinition.includes(`[${luaGenerator.quote_(model.name)}] = ${luaGenerator.quote_(luaGenerator.getVariableName(model.getId()))}`))
    }
    assert.ok(functionDefinition.includes(`['计数'] = ${luaGenerator.quote_(luaGenerator.getProcedureName('计数'))}`))
    assert.ok(!variableDefinition.includes('仅参数'))
    assert.ok(!functionDefinition.includes("['a-b']"))
    luaGenerator.finish('')
  } finally {
    workspace.dispose()
  }
})

test('reflection helpers are local, deterministic and absent from unrelated workspaces', () => {
  const workspace = new Blockly.Workspace()
  try {
    lookup(workspace, 'reflection_get_global', "'计数'")
    lookup(workspace, 'reflection_get_global', "'other'")
    const code = luaGenerator.workspaceToCode(workspace)
    assert.equal(luaGenerator.workspaceToCode(workspace), code)
    assert.equal((code.match(/local mlua_reflection_variable =/g) || []).length, 1)
    assert.equal((code.match(/local function mlua_reflection_name\(/g) || []).length, 1)
  } finally {
    workspace.dispose()
  }
  assert.ok(!generate(workspace => assign(workspace, 'plain', '42')).includes('mlua_reflection'))
})

const repoRoot = fileURLToPath(new URL('../../../', import.meta.url))
const python = fileURLToPath(new URL(process.platform === 'win32'
  ? '../../../.venv/Scripts/python.exe' : '../../../.venv/bin/python', import.meta.url))

test('generated Lua preserves reflected names, callable objects, nil slots and task snapshots', {
  skip: !existsSync(python) && 'project Python environment is unavailable',
}, () => {
  const cases = []
  const add = (name, expected, build) => cases.push({ name, expected, code: generate(build) })

  add('distinct final names and separate variable/function mappings', true, workspace => {
    const steps = []
    for (const [index, name] of ['计数', 'a-b', 'a b', 'end', '1abc', "a'b", 'mlua_reflection_name'].entries()) {
      steps.push(assign(workspace, name, String(index + 10)))
      steps.push(statement(workspace, `assert(%s == ${index + 10})`, lookup(workspace, 'reflection_get_global', luaGenerator.quote_(name))))
    }
    define(workspace, '计数', value(workspace, '42'))
    define(workspace, 'end', value(workspace, '43'))
    steps.push(statement(workspace, 'assert(%s == 42)', call(workspace, lookup(workspace, 'reflection_get_function', "'计' .. '数'"))))
    steps.push(statement(workspace, 'assert(%s == 43)', call(workspace, lookup(workspace, 'reflection_get_function', "'end'"))))
    steps.push(statement(workspace, 'return true'))
    chain(...steps)
  })
  add('raw UTF-8 keys, false values and missing locals', true, workspace => {
    const setup = statement(workspace, "_G['计数'] = 99; _G['false_value'] = false; local hidden = 7")
    const setter = assign(workspace, '计数', '42')
    const raw = statement(workspace, 'assert(%s == 99)', lookup(workspace, 'reflection_get_global', "'计数'", 'RAW'))
    const mapped = statement(workspace, 'assert(%s == 42)', lookup(workspace, 'reflection_get_global', "'计数'"))
    const falsy = statement(workspace, 'assert(%s == false)', lookup(workspace, 'reflection_get_global', "'false_value'", 'RAW'))
    const local = statement(workspace, 'assert(%s == nil)', lookup(workspace, 'reflection_get_global', "'hidden'", 'RAW'))
    const missing = statement(workspace, 'return %s == nil', lookup(workspace, 'reflection_get_global', "'不存在'"))
    chain(setup, setter, raw, mapped, falsy, local, missing)
  })
  add('shared Chinese keys and one evaluation of the name', '大厅', workspace => {
    chain(statement(workspace, 'shared.set_key("当前场景", "大厅"); lookups = 0; function key() lookups = lookups + 1; return "当前" .. "场景" end'),
      assign(workspace, 'answer', 'nil'),
      statement(workspace, 'answer = %s; assert(lookups == 1); return answer', lookup(workspace, 'reflection_get_shared', 'key()')))
  })
  add('Python host callables', 42, workspace => {
    statement(workspace, 'return %s', call(workspace, lookup(workspace, 'reflection_get_function', "'host_double'", 'RAW'), '{21}'))
  })
  add('default function reference from the toolbox', 42, workspace => {
    define(workspace, '执行任务', value(workspace, '42'))
    const spec = luaReflectionBlocks.find(spec => spec.type === 'reflection_call_return')
    const invocation = Blockly.serialization.blocks.append({ type: spec.type, inputs: spec.toolboxInputs }, workspace)
    invocation.getInputTargetBlock('FUNCTION').getInputTargetBlock('NAME').setFieldValue('执行任务', 'VALUE')
    statement(workspace, 'return %s', invocation)
  })
  add('function references stored in ordinary variables', 42, workspace => {
    define(workspace, '执行任务', value(workspace, '42'))
    const setter = assign(workspace, '函数引用', lookup(workspace, 'reflection_get_function', "'执行任务'"))
    const variable = workspace.newBlock('variables_get')
    variable.setFieldValue(setter.getFieldValue('VAR'), 'VAR')
    chain(setter, statement(workspace, 'return %s', call(workspace, variable)))
  })
  add('callable table and ignored results', true, workspace => {
    chain(statement(workspace, 'callable = setmetatable({}, {__call = function(_, value) shared.set_key("called", value); return 9 end})'),
      call(workspace, lookup(workspace, 'reflection_get_function', "'callable'", 'RAW'), '{true}', 'reflection_call'),
      statement(workspace, 'return %s', lookup(workspace, 'reflection_get_shared', "'called'")))
  })
  add('zero arguments', 0, workspace => {
    chain(statement(workspace, 'function count(...) return select("#", ...) end'),
      statement(workspace, 'return %s', call(workspace, lookup(workspace, 'reflection_get_function', "'count'", 'RAW'))))
  })
  add('nil arguments and multiple results', [3, null, false, null], workspace => {
    chain(statement(workspace, 'function echo(...) return select("#", ...), ... end'),
      statement(workspace, 'return %s', call(workspace, lookup(workspace, 'reflection_get_function', "'echo'", 'RAW'), 'table.pack(nil, false, nil)')))
  })
  add('local mapping closures survive thread snapshots', 42, workspace => {
    define(workspace, '执行任务', lookup(workspace, 'reflection_get_global', "'counter'"))
    define(workspace, '子任务', call(workspace, lookup(workspace, 'reflection_get_function', "'执行任务'")))
    const task = workspace.newBlock('reflection_test_run_task')
    task.setFieldValue('子任务', 'NAME')
    chain(assign(workspace, 'counter', '42'), statement(workspace, 'return %s', task))
  })
  add('shared Chinese keys remain available in child tasks', 42, workspace => {
    define(workspace, '子任务', lookup(workspace, 'reflection_get_shared', "'任务结果'"))
    const task = workspace.newBlock('reflection_test_run_task')
    task.setFieldValue('子任务', 'NAME')
    chain(statement(workspace, 'shared.set_key("任务结果", 42)'), statement(workspace, 'return %s', task))
  })
  add('reflection preserves existing private-global snapshot isolation', true, workspace => {
    define(workspace, '子任务', lookup(workspace, 'reflection_get_global', "'计数'"))
    const task = workspace.newBlock('reflection_test_run_task')
    task.setFieldValue('子任务', 'NAME')
    chain(assign(workspace, '计数', '42'), statement(workspace, 'return %s == nil', task))
  })
  const modules = ['a b', 'a-b'].map((name, index) => generate(workspace => {
    workspace.getVariableMap().createVariable(name)
    define(workspace, `read${index}`, lookup(workspace, 'reflection_get_global', luaGenerator.quote_(name)))
    statement(workspace, `return { read = read${index} }`)
  }))
  cases.push({ name: 'module mappings do not overwrite each other', expected: true, code:
    `package.preload.first = function()\n${modules[0]}\nend\n`
    + `package.preload.second = function()\n${modules[1]}\nend\n`
    + 'local first, second = require("first"), require("second"); a_b = 42; return first.read() == 42 and second.read() == 42' })

  for (const type of ['reflection_get_global', 'reflection_get_function', 'reflection_get_shared']) {
    cases.push({ name: `reject non-string ${type}`, error: '反射名称必须是字符串', code:
      generate(workspace => statement(workspace, 'return %s', lookup(workspace, type, '42'))) })
  }
  for (const [target, args, error] of [
    ['nil', '{}', 'attempt to call a nil value'],
    ['42', '{}', 'attempt to call a number value'],
    ['host_double', 'false', '反射调用的参数必须是列表'],
    ['host_double', '{n = -1}', '反射调用的参数数量必须是非负整数'],
    ['host_double', '{n = 1.5}', '反射调用的参数数量必须是非负整数'],
  ]) {
    cases.push({ name: `invalid call ${target} ${args}`, error, code:
      generate(workspace => statement(workspace, 'return %s', call(workspace, value(workspace, target), args))) })
  }

  const result = execFileSync(python, ['-B', '-c', `
import json, sys
from pathlib import Path
from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.utils.table_lua import lua_2_python
class Host:
    def print(self, message): pass
    def write(self, data): pass
    def log(self, level, message): pass
    def notify(self, message): pass
    def check_stop(self): pass
    def clear_output(self): pass
    def set_output_limit(self, limit): return limit
    def get_output_limit(self): return 300
cases = json.load(sys.stdin)
for case in cases:
    engine = LuaEngine(Path.cwd(), Host())
    engine.inject().globals()['host_double'] = lambda value: value * 2
    try:
        try:
            result = lua_2_python(engine.execute(case['code']))
        except Exception as exc:
            assert 'error' in case and case['error'] in str(exc), (case['name'], str(exc))
        else:
            assert 'error' not in case, case['name']
            assert result == case['expected'], (case['name'], result, case['expected'])
    finally:
        assert engine.shutdown_threads(timeout=2), case['name']
print(len(cases))
`], {
    cwd: repoRoot,
    input: JSON.stringify(cases),
    encoding: 'utf8',
    env: { ...process.env, PYTHONPATH: fileURLToPath(new URL('../../../src', import.meta.url)), PYTHONIOENCODING: 'utf-8' },
    timeout: 30_000,
  })
  assert.equal(Number(result.trim()), cases.length)
})
