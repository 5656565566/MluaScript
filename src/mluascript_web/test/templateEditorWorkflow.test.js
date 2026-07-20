import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { useTemplateEditor } from '../src/ui/templateEditor/useTemplateEditor.js'

function createEditor(data) {
  return useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(true),
      templateEditorModalData: ref(data),
    },
    message: { success() {}, warning() {} },
    getProcedureDefinitions: () => [],
    closeEditor() {},
    saveEditorMeta() {},
  })
}

test('template editor exposes only canonical data types and path as a string UI style', () => {
  const editor = createEditor({ vars: {}, tasks: [], flows: [] })

  assert.deepEqual(editor.tpOptions.map(option => option.value), ['str', 'int', 'num', 'bool', 'enum', 'json'])
  assert.deepEqual(editor.strUiOptions.map(option => option.value), ['', 'path'])
})

test('adding a workflow step keeps task parameters and flow globals untouched', () => {
  const editor = createEditor({
    vars: { stage: { tp: 'str', def: '1-7' }, retry: { tp: 'int', def: 2 } },
    tasks: [{ k: 'battle', args: ['stage', 'retry'] }],
    flows: [{ k: 'main', g: [], steps: [] }],
  })

  editor.addStep()

  assert.deepEqual(editor.selectedStep.value.args, {})
  assert.deepEqual(editor.selectedFlow.value.g, [])
  assert.deepEqual(editor.stepBindingStats.value, { total: 0, complete: 0 })
  assert.equal(editor.isStepBindingComplete(editor.selectedStep.value), true)
})

test('step parameter overrides are created explicitly without changing flow globals', () => {
  const editor = createEditor({
    vars: { stage: { tp: 'str', def: '1-7' } },
    tasks: [{ k: 'battle', args: ['stage'] }],
    flows: [{ k: 'main', g: [], steps: [{ k: 'battle_1', task: 'battle', args: {} }] }],
  })

  editor.openStepArgsPicker(editor.selectedFlow.value, editor.selectedStep.value)
  editor.stepArgEditorState.value.selectedKeys = ['stage']
  editor.stepArgEditorState.value.rows[0].binding = { $bind: 'literal', value: '2-1' }
  editor.confirmStepArgEditor()

  assert.deepEqual(editor.selectedStep.value.args, { stage: { $bind: 'literal', value: '2-1' } })
  assert.deepEqual(editor.selectedFlow.value.g, [])
  assert.deepEqual(editor.stepBindingStats.value, { total: 1, complete: 1 })
})

test('step overrides can only reference parameters exposed by the selected flow', () => {
  const editor = createEditor({
    vars: {
      stage: { t: '关卡', tp: 'str', def: '1-7' },
      retry: { t: '重试次数', tp: 'int', def: 2 },
    },
    tasks: [{ k: 'battle', args: ['retry'] }],
    flows: [{
      k: 'main',
      g: ['stage'],
      steps: [{ k: 'battle_1', task: 'battle', args: { retry: { $bind: 'var', key: 'retry' } } }],
    }],
  })

  assert.deepEqual(editor.stepArgSourceOptions.value, [
    { label: '直接填写固定值', value: '__literal__' },
    { label: '关卡 (stage)', value: 'stage' },
  ])
  assert.equal(editor.bindingSourceOptions.value[0].disabled, false)
  assert.deepEqual(editor.stepBindingStats.value, { total: 1, complete: 0 })

  editor.setStepArgSource('retry', 'var')

  assert.deepEqual(editor.selectedStep.value.args.retry, { $bind: 'var', key: 'stage' })
  assert.deepEqual(editor.selectedFlow.value.g, ['stage'])

  editor.selectedFlow.value.g = []
  assert.equal(editor.bindingSourceOptions.value[0].disabled, true)
  assert.deepEqual(editor.stepArgSourceOptions.value, [
    { label: '直接填写固定值', value: '__literal__' },
  ])
})

test('renaming a workflow step keeps success, failure, and parameter branch targets valid', () => {
  const editor = createEditor({
    tasks: [{ k: 'battle', args: [] }],
    flows: [{
      k: 'main',
      steps: [
        { k: 'battle_1', task: 'battle' },
        {
          k: 'check_1',
          task: 'battle',
          onSuccess: 'goto',
          successGoto: 'battle_1',
          onFail: 'goto',
          goto: 'battle_1',
          successBranches: [{ if: { k: 'mode', eq: 'safe' }, goto: 'battle_1' }],
        },
      ],
    }],
  })

  editor.setSelectedStepKey('battle_main')

  assert.equal(editor.selectedFlow.value.steps[1].goto, 'battle_main')
  assert.equal(editor.selectedFlow.value.steps[1].successGoto, 'battle_main')
  assert.equal(editor.selectedFlow.value.steps[1].successBranches[0].goto, 'battle_main')
})

test('workflow branch controls follow parameter types and preserve lock state', () => {
  const editor = createEditor({
    vars: {
      count: { t: '次数', tp: 'int', def: 1 },
      mode: { t: '模式', tp: 'enum', def: 'safe', oneOf: [{ v: 'safe', t: '安全' }, { v: 'fast', t: '快速' }] },
    },
    tasks: [{ k: 'run', args: [] }],
    flows: [{
      k: 'main',
      g: ['count', 'mode'],
      lockSteps: true,
      steps: [{ k: 'check', task: 'run' }, { k: 'finish', task: 'run' }],
    }],
  })

  editor.addWorkflowBranch()
  const branch = editor.selectedStep.value.successBranches[0]
  assert.equal(editor.selectedFlow.value.lockSteps, true)
  assert.equal(branch.if.k, 'count')
  assert.equal(branch.goto, 'check')
  assert.deepEqual(editor.workflowBranchOperatorOptions(branch).map(option => option.value), ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'])
  assert.equal(editor.workflowBranchValueControl(branch), 'number')

  editor.setWorkflowBranchParameter(branch, 'mode')
  editor.setWorkflowBranchOperator(branch, 'in')
  editor.setWorkflowBranchValue(branch, ['safe', 'fast'])
  assert.equal(editor.workflowBranchValueControl(branch), 'select')
  assert.equal(editor.workflowBranchValueMultiple(branch), true)
  assert.deepEqual(editor.workflowBranchValue(branch), ['safe', 'fast'])
})

test('resource dialog key edits keep task and variable references valid', () => {
  const editor = createEditor({
    vars: { stage: { tp: 'str' } },
    tasks: [{ k: 'battle', args: ['stage'] }],
    flows: [{
      k: 'main',
      g: ['stage'],
      steps: [{ k: 'battle_1', task: 'battle', args: { stage: { $bind: 'var', key: 'stage' } } }],
    }],
  })

  const variable = editor.varsList.value[0]
  const task = editor.localData.value.tasks[0]
  editor.setVariableKey(variable, '')
  editor.setVariableKey(variable, 'level')
  editor.setTaskKey(task, '')
  editor.setTaskKey(task, 'fight')

  assert.deepEqual(task.args, ['level'])
  assert.deepEqual(editor.selectedFlow.value.g, ['level'])
  assert.equal(editor.selectedStep.value.task, 'fight')
  assert.deepEqual(editor.selectedStep.value.args, { level: { $bind: 'var', key: 'level' } })
})
