import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveProcedureArgumentLuaName } from '../src/blockly/procedureArgumentName.js'

function createProcedureBlock(names) {
  return {
    getVarModels: () => names.map((name, index) => ({
      getName: () => name,
      getId: () => `arg_${index}`,
    })),
  }
}

test('函数参数使用 VariableModel ID 获取 Lua 名称', () => {
  const generator = {
    getVariableName: id => ({
      arg_0: '_E5_8F_82_E6_95_B0',
      arg_1: 'end2',
    })[id],
  }
  const block = createProcedureBlock(['参数', 'end'])

  assert.equal(resolveProcedureArgumentLuaName(block, '参数', generator), '_E5_8F_82_E6_95_B0')
  assert.equal(resolveProcedureArgumentLuaName(block, 'end', generator), 'end2')
})

test('不存在的函数参数不会生成错误标识符', () => {
  const generator = { getVariableName: id => id }
  assert.equal(resolveProcedureArgumentLuaName(createProcedureBlock(['args']), 'missing', generator), '')
})
