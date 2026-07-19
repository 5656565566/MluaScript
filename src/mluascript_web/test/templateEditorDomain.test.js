import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTemplatePayload,
  countTaskReferences,
  countVariableReferences,
  createStepArgBinding,
  flattenParsedVars,
  normalizeTemplateEditorData,
  removeTaskReferences,
  removeVariableReferences,
  renameVariableReferences,
  validateTemplateDraft,
} from '../src/features/templates/editor/templateEditorDomain.js'

test('template editor data survives normalization and serialization', () => {
  const source = {
    v: 1,
    id: 'daily',
    vars: {
      mode: {
        t: 'Mode',
        tp: 'enum',
        oneOf: [{ v: 'fast', t: 'Fast', children: [{ k: 'count', tp: 'int', def: 2 }] }],
      },
    },
    tasks: [{ k: 'run', fn: 'run_task', args: ['mode', 'count'] }],
    flows: [{ k: 'main', g: ['mode'], steps: [{ k: 'step', task: 'run', args: { count: 3 } }] }],
  }

  const normalized = normalizeTemplateEditorData(source)
  const payload = buildTemplatePayload(normalized.localData, normalized.varsList)

  assert.equal(normalized.varsList.length, 2)
  assert.equal(payload.id, source.id)
  assert.deepEqual(payload.vars.mode.oneOf[0].children, [{
    k: 'count',
    t: '',
    tp: 'int',
    req: false,
    note: '',
    def: 2,
  }])
  assert.deepEqual(payload.tasks[0].args, ['mode', 'count'])
  assert.deepEqual(payload.flows[0].steps[0].args, { count: 3 })
})

test('template editor serializes canonical numeric, json, and path-style string fields', () => {
  const normalized = normalizeTemplateEditorData({
    vars: {
      ratio: { tp: 'num', def: 0.5, min: 0, max: 1 },
      payload: { tp: 'json', def: '{"mode":"safe"}' },
      file: { tp: 'str', ui: 'path', def: 'demo.json' },
    },
  })
  const payload = buildTemplatePayload(normalized.localData, normalized.varsList)

  assert.deepEqual(payload.vars.ratio, {
    t: '', tp: 'num', req: false, note: '', def: 0.5, min: 0, max: 1,
  })
  assert.deepEqual(payload.vars.payload, {
    t: '', tp: 'json', req: false, note: '', def: '{"mode":"safe"}',
  })
  assert.deepEqual(payload.vars.file, {
    t: '', tp: 'str', req: false, note: '', ui: 'path', def: 'demo.json',
  })
})

test('step parameter overrides and transition targets survive serialization', () => {
  const source = {
    id: 'binding-demo',
    vars: { stage: { tp: 'str', def: '1-7' } },
    tasks: [{ k: 'battle', fn: 'run_battle', args: ['stage'] }],
    flows: [{
      k: 'main',
      steps: [{
        k: 'battle_1',
        task: 'battle',
        args: { stage: createStepArgBinding('var', 'stage') },
        onSuccess: 'goto',
        successGoto: 'battle_2',
        onFail: 'goto',
        goto: 'battle_1',
      }],
    }],
  }

  const normalized = normalizeTemplateEditorData(source)
  const payload = buildTemplatePayload(normalized.localData, normalized.varsList)

  assert.deepEqual(payload.flows[0].steps[0].args.stage, { $bind: 'var', key: 'stage' })
  assert.equal(payload.flows[0].steps[0].onSuccess, 'goto')
  assert.equal(payload.flows[0].steps[0].successGoto, 'battle_2')
  assert.equal(payload.flows[0].steps[0].onFail, 'goto')
  assert.equal(payload.flows[0].steps[0].goto, 'battle_1')
})

test('renaming a variable updates tasks, flows, conditions, and step values', () => {
  const varsList = flattenParsedVars({ enabled: { tp: 'bool' }, child: { tp: 'str', if: { k: 'enabled', eq: true } } })
  const localData = {
    tasks: [{ args: ['enabled'] }],
    flows: [{ g: ['enabled'], steps: [{ args: { enabled: 'enabled' } }] }],
  }

  renameVariableReferences({ varsList, localData, from: 'enabled', to: 'active' })

  assert.equal(varsList[1].if.k, 'active')
  assert.deepEqual(localData.tasks[0].args, ['active'])
  assert.deepEqual(localData.flows[0].g, ['active'])
  assert.deepEqual(localData.flows[0].steps[0].args, { active: 'active' })
})

test('deleting a variable clears every dependent template reference', () => {
  const varsList = flattenParsedVars({
    enabled: { tp: 'bool' },
    child: { tp: 'str', if: { k: 'enabled', eq: true } },
  })
  const localData = {
    tasks: [{ k: 'run', args: ['enabled'] }],
    flows: [{
      k: 'main',
      g: ['enabled'],
      steps: [{
        k: 'run_1',
        task: 'run',
        args: {
          enabled: createStepArgBinding('literal', true),
          child: createStepArgBinding('var', 'enabled'),
        },
      }],
    }],
  }

  assert.equal(countVariableReferences({ varsList, localData, key: 'enabled' }), 5)
  removeVariableReferences({ varsList, localData, key: 'enabled' })

  assert.equal(varsList[1].if, null)
  assert.deepEqual(localData.tasks[0].args, [])
  assert.deepEqual(localData.flows[0].g, [])
  assert.deepEqual(localData.flows[0].steps[0].args, {})
})

test('deleting a task removes its flow instances and repairs goto targets', () => {
  const localData = {
    tasks: [{ k: 'run' }, { k: 'finish' }],
    flows: [{
      k: 'main',
      steps: [
        { k: 'run_1', task: 'run' },
        {
          k: 'finish_1',
          task: 'finish',
          onSuccess: 'goto',
          successGoto: 'run_1',
          onFail: 'goto',
          goto: 'run_1',
        },
      ],
    }],
  }

  assert.equal(countTaskReferences(localData, 'run'), 1)
  removeTaskReferences(localData, 'run')

  assert.deepEqual(localData.flows[0].steps, [{
    k: 'finish_1',
    task: 'finish',
    onSuccess: 'continue',
    successGoto: '',
    onFail: 'stop',
    goto: '',
  }])
})

test('template validation rejects blank, duplicate, and dangling identifiers', () => {
  const errors = validateTemplateDraft({
    tasks: [
      { k: 'run', args: ['missing'] },
      { k: 'run', args: [] },
    ],
    flows: [{
      k: '',
      g: ['missing'],
      steps: [{
        k: '',
        task: 'missing_task',
        args: { undeclared: createStepArgBinding('var', 'missing') },
        onSuccess: 'goto',
        successGoto: 'missing_step',
        onFail: 'goto',
        goto: '',
      }],
    }],
  }, [
    { _key: 'mode' },
    { _key: 'mode' },
    { _key: '', if: { k: 'missing' } },
  ])

  assert.ok(errors.includes('参数 Key 重复：mode'))
  assert.ok(errors.includes('参数 3 缺少 Key'))
  assert.ok(errors.includes('任务 Key 重复：run'))
  assert.ok(errors.includes('任务流 1 缺少 Key'))
  assert.ok(errors.some(error => error.includes('引用了不存在的参数：missing')))
  assert.ok(errors.some(error => error.includes('引用了不存在的任务：missing_task')))
  assert.ok(errors.some(error => error.includes('成功跳转目标不存在：missing_step')))
})

test('template validation accepts a complete flow with explicit overrides', () => {
  const errors = validateTemplateDraft({
    tasks: [{ k: 'battle', fn: 'run_battle', args: ['stage'] }],
    flows: [{
      k: 'main',
      g: ['stage'],
      steps: [{
        k: 'battle_1',
        task: 'battle',
        args: { stage: createStepArgBinding('var', 'stage') },
        onSuccess: 'continue',
        successGoto: '',
        onFail: 'stop',
        goto: '',
      }],
    }],
  }, [{ _key: 'stage' }], { procedureNames: ['run_battle'] })

  assert.deepEqual(errors, [])
})

test('template validation rejects blank and stale Blockly function references', () => {
  const errors = validateTemplateDraft({
    tasks: [
      { k: 'blank', fn: '', args: [] },
      { k: 'stale', fn: 'removed_function', args: [] },
    ],
    flows: [],
  }, [], { procedureNames: ['available_function'] })

  assert.ok(errors.includes('任务 blank 未选择 Blockly 函数'))
  assert.ok(errors.includes('任务 stale 引用的 Blockly 函数不存在：removed_function'))
})
