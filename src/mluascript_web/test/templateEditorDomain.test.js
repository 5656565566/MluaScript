import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTemplatePayload,
  createStepArgBinding,
  flattenParsedVars,
  normalizeTemplateEditorData,
  renameVariableReferences,
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
