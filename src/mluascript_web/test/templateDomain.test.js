import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTemplateFieldRows,
  buildWorkflowDefaults,
  isTemplateConditionActive,
  normalizeRuntimeValue,
  normalizeTemplateMeta,
} from '../src/features/templates/templateDomain.js'

test('template metadata normalizes compact backend fields', () => {
  const meta = normalizeTemplateMeta({
    t: 'Demo',
    vars: { count: { tp: 'int', def: 2 } },
    tasks: [{ k: 'task', t: 'Task', args: ['count'] }],
    flows: [{ k: 'main', steps: [{ k: 'step', task: 'task' }] }],
  })

  assert.equal(meta.title, 'Demo')
  assert.equal(meta.type, 'workflow-template')
  assert.equal(meta.workflows[0].tasks[0].fields[0].default, 2)
})

test('workflow defaults preserve saved order and append new steps', () => {
  const meta = normalizeTemplateMeta({
    vars: {},
    tasks: [{ k: 'task', args: [] }],
    flows: [{ k: 'main', steps: [{ k: 'a', task: 'task' }, { k: 'b', task: 'task' }] }],
  })
  const defaults = buildWorkflowDefaults(meta, { flows: { main: { stepOrder: ['b'] } } })
  assert.deepEqual(defaults.main.stepOrder, ['b', 'a'])
})

test('locked workflow defaults ignore saved order and enabled state', () => {
  const meta = normalizeTemplateMeta({
    vars: {},
    tasks: [{ k: 'task', args: [] }],
    flows: [{
      k: 'main',
      lockSteps: true,
      steps: [{ k: 'a', task: 'task', enabled: true }, { k: 'b', task: 'task', enabled: false }],
    }],
  })
  const defaults = buildWorkflowDefaults(meta, {
    flows: { main: { stepOrder: ['b', 'a'], stepEnabled: { a: false, b: true } } },
  })

  assert.equal(meta.workflows[0].lockSteps, true)
  assert.deepEqual(defaults.main.stepOrder, ['a', 'b'])
  assert.deepEqual(defaults.main.stepEnabled, { a: true, b: false })
})

test('workflow defaults resolve parameter and literal binding descriptors', () => {
  const meta = normalizeTemplateMeta({
    vars: {
      stage: { tp: 'str', def: '1-7' },
      retry: { tp: 'int', def: 2 },
    },
    tasks: [{ k: 'battle', args: ['stage', 'retry'] }],
    flows: [{
      k: 'main',
      g: ['stage'],
      steps: [{
        k: 'battle_1',
        task: 'battle',
        args: {
          stage: { $bind: 'var', key: 'stage' },
          retry: { $bind: 'literal', value: 3 },
        },
      }],
    }],
  })

  const defaults = buildWorkflowDefaults(meta, { flows: { main: { globals: { stage: '2-1' } } } })

  assert.deepEqual(defaults.main.stepArgs.battle_1, { stage: '2-1', retry: 3 })
})

test('runtime values normalize numeric and structured inputs', () => {
  assert.equal(normalizeRuntimeValue({ tp: 'int' }, '2.9'), 2)
  assert.equal(normalizeRuntimeValue({ tp: 'num' }, '2.9'), 2.9)
  assert.deepEqual(normalizeRuntimeValue({ tp: 'json' }, '[1, 2]'), [1, 2])
})

test('runtime conditions apply numeric comparisons and enum sets', () => {
  assert.equal(isTemplateConditionActive({ k: 'count', gt: 2 }, 3), true)
  assert.equal(isTemplateConditionActive({ k: 'count', gte: 3 }, 3), true)
  assert.equal(isTemplateConditionActive({ k: 'count', lt: 3 }, 3), false)
  assert.equal(isTemplateConditionActive({ k: 'count', lte: 3 }, 3), true)
  assert.equal(isTemplateConditionActive({ k: 'count', gt: -1 }, null), false)
  assert.equal(isTemplateConditionActive({ k: 'count', gt: 2 }, '3'), false)
  assert.equal(isTemplateConditionActive({ k: 'mode', in: ['debug', 'trace'] }, 'trace'), true)
})

test('path is a string input style instead of a standalone type', () => {
  const meta = normalizeTemplateMeta({
    vars: { file: { tp: 'str', ui: 'path' } },
    tasks: [{ k: 'task', args: ['file'] }],
    flows: [{ k: 'main', steps: [{ k: 'step', task: 'task' }] }],
  })

  assert.equal(meta.vars.file.rawType, 'str')
  assert.equal(meta.vars.file.type, 'string')
  assert.equal(meta.vars.file.ui, 'path')
})

test('task parameter relations do not leak to another task', () => {
  const meta = normalizeTemplateMeta({
    vars: {
      test: { tp: 'bool', def: false },
      gugu: { tp: 'str', def: '' },
    },
    tasks: [
      { k: 'task_a', args: ['test', { k: 'gugu', if: { k: 'test', eq: true } }] },
      { k: 'task_b', args: ['gugu'] },
    ],
    flows: [{
      k: 'main',
      steps: [
        { k: 'a1', task: 'task_a' },
        { k: 'b1', task: 'task_b' },
      ],
    }],
  })

  const [taskA, taskB] = meta.workflows[0].tasks
  assert.deepEqual(taskA.fields.find(field => field.key === 'gugu').if, {
    k: 'test',
    eq: true,
    in: [],
  })
  assert.equal(taskB.fields.find(field => field.key === 'gugu').if, null)
})

test('field rows preserve arbitrary dependency depth and ancestor activation', () => {
  const fields = [
    { key: 'leaf', if: { k: 'child', eq: true } },
    { key: 'root' },
    { key: 'child', if: { k: 'root', eq: true } },
  ]

  const hiddenRows = buildTemplateFieldRows(fields, key => ({ root: false, child: true }[key]))
  assert.deepEqual(hiddenRows.map(field => [field.key, field.dependencyDepth, field.dependencyActive]), [
    ['root', 0, true],
    ['child', 1, false],
    ['leaf', 2, false],
  ])

  const visibleRows = buildTemplateFieldRows(fields, key => ({ root: true, child: true }[key]))
  assert.deepEqual(visibleRows.map(field => [field.key, field.dependencyDepth, field.dependencyActive]), [
    ['root', 0, true],
    ['child', 1, true],
    ['leaf', 2, true],
  ])
})
