import test from 'node:test'
import assert from 'node:assert/strict'

import { getBlockSemanticDiagnostic } from '../src/blockly/blockSemanticDiagnostics.js'
import { setProjectModuleRegistry } from '../src/features/projects/projectModuleRegistry.js'

function createBlock(type, fields = {}, extra = {}) {
  return {
    type,
    getFieldValue(name) {
      return fields[name] || ''
    },
    ...extra,
  }
}

function createWorkspace(blocks) {
  return {
    getTopBlocks() {
      return blocks
    },
  }
}

test('required module and file picker blocks report semantic errors', () => {
  assert.equal(
    getBlockSemanticDiagnostic(createBlock('lua_require_module_stmt')),
    '请选择要导入的模块',
  )
  assert.equal(
    getBlockSemanticDiagnostic(createBlock('lua_dofile_stmt')),
    '请选择要执行的 Lua 文件',
  )
})

test('thread spawn only accepts one function call', () => {
  const empty = createBlock('thread_spawn_function', {}, { getInputTargetBlock: () => null })
  assert.equal(getBlockSemanticDiagnostic(empty), '请嵌入一个函数调用块')

  const invalid = createBlock('thread_spawn_function', {}, {
    getInputTargetBlock: () => createBlock('lua_print'),
  })
  assert.equal(getBlockSemanticDiagnostic(invalid), '这里只能嵌入函数调用块')

  const chainedCall = createBlock('procedures_callnoreturn', {}, { getNextBlock: () => createBlock('lua_print') })
  const chained = createBlock('thread_spawn_function', {}, { getInputTargetBlock: () => chainedCall })
  assert.equal(getBlockSemanticDiagnostic(chained), '后台任务只能包含一个函数调用块')
})

test('module exports reject missing function references', () => {
  const procedure = createBlock('procedures_defnoreturn', { NAME: 'available' })
  const exportBlock = createBlock('lua_module_export_function', {
    FUNC_VALUES: JSON.stringify(['removed']),
  })
  const workspace = createWorkspace([procedure, exportBlock])
  exportBlock.workspace = workspace

  assert.equal(getBlockSemanticDiagnostic(exportBlock), '导出函数不存在：removed')
})

test('template tasks reject blank and stale function references', () => {
  const procedure = createBlock('procedures_defnoreturn', { NAME: 'available' })
  const templateBlock = createBlock('maa_template_config', {
    TEMPLATE_JSON: JSON.stringify({ tasks: [{ k: 'battle', fn: 'removed' }] }),
  })
  const workspace = createWorkspace([procedure, templateBlock])
  templateBlock.workspace = workspace

  assert.equal(
    getBlockSemanticDiagnostic(templateBlock),
    '任务 battle 引用的 Blockly 函数不存在：removed',
  )
})

test('project module calls track exported parameters and return shape', () => {
  setProjectModuleRegistry([{
    key: 'lib/math',
    exports: [{ name: 'add', params: ['a', 'b'], hasReturn: true }],
  }, {
    key: 'lib/log',
    exports: [{ name: 'write', params: ['message'], hasReturn: false }],
  }])

  const valid = createBlock('lua_project_module_call_expr', {
    MODULE_VALUE: 'lib/math',
    FUNCTION_VALUE: 'add',
    PARAM_VALUES: JSON.stringify(['a', 'b']),
  })
  const stale = createBlock('lua_project_module_call_stmt', {
    MODULE_VALUE: 'lib/math',
    FUNCTION_VALUE: 'add',
    PARAM_VALUES: JSON.stringify(['value']),
  })
  const noReturn = createBlock('lua_project_module_call_expr', {
    MODULE_VALUE: 'lib/log',
    FUNCTION_VALUE: 'write',
    PARAM_VALUES: JSON.stringify(['message']),
  })

  assert.equal(getBlockSemanticDiagnostic(valid), '')
  assert.match(getBlockSemanticDiagnostic(stale), /参数已变化/)
  assert.match(getBlockSemanticDiagnostic(noReturn), /没有返回值/)
  setProjectModuleRegistry([])
})
