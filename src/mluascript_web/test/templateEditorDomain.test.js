import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTemplatePayload,
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
