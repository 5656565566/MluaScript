import assert from 'node:assert/strict'
import test from 'node:test'

import {
  deleteWorkspaceVariableById,
  getWorkspaceAllVariables,
  getWorkspaceVariableById,
  getWorkspaceVariablesOfType,
} from '../src/blockly/workspaceVariables.js'

function createWorkspaceVariables() {
  const variables = [
    { id: 'global-id', type: '', name: 'global' },
    { id: 'typed-id', type: 'number', name: 'typed' },
  ]
  const variableMap = {
    getVariablesOfType(type) {
      return variables.filter((variable) => variable.type === type)
    },
    getAllVariables() {
      return [...variables]
    },
    getVariableById(id) {
      return variables.find((variable) => variable.id === id) || null
    },
    deleteVariable(variable) {
      variables.splice(variables.indexOf(variable), 1)
    },
  }
  return {
    workspace: {
      getVariableMap() {
        return variableMap
      },
    },
    variables,
  }
}

test('通过 Blockly 13 VariableMap 读取工作区变量', () => {
  const { workspace } = createWorkspaceVariables()

  assert.deepEqual(getWorkspaceVariablesOfType(workspace), [
    { id: 'global-id', type: '', name: 'global' },
  ])
  assert.equal(getWorkspaceAllVariables(workspace).length, 2)
  assert.equal(getWorkspaceVariableById(workspace, 'typed-id')?.name, 'typed')
})

test('通过 Blockly 13 VariableMap 删除工作区变量', () => {
  const { workspace, variables } = createWorkspaceVariables()

  assert.equal(deleteWorkspaceVariableById(workspace, 'global-id'), true)
  assert.deepEqual(variables.map((variable) => variable.id), ['typed-id'])
  assert.equal(deleteWorkspaceVariableById(workspace, 'missing-id'), false)
})

test('工作区未初始化时变量访问返回安全空值', () => {
  assert.deepEqual(getWorkspaceVariablesOfType(null), [])
  assert.deepEqual(getWorkspaceAllVariables(undefined), [])
  assert.equal(getWorkspaceVariableById(null, 'id'), null)
  assert.equal(deleteWorkspaceVariableById(undefined, 'id'), false)
})
