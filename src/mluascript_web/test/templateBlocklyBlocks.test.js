import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const blocksUrl = new URL('../src/blockly/blocks/template.js', import.meta.url)
const utilsUrl = new URL('../src/blockly/utils.js', import.meta.url)

test('template category owns dedicated state and workflow parameter blocks', async () => {
  const [blocks, utils] = await Promise.all([
    readFile(blocksUrl, 'utf8'),
    readFile(utilsUrl, 'utf8'),
  ])

  assert.match(blocks, /type: 'template_state_get'[\s\S]*category: '模板'[\s\S]*shared\.get_key\("template_state"\)/)
  assert.match(blocks, /type: 'template_workflow_global_get'[\s\S]*shared\.get_key\("template_workflow_globals"\)/)
  assert.match(blocks, /type: 'template_workflow_global_set'[\s\S]*shared\.set_key\("template_workflow_globals"/)
  assert.match(blocks, /关联任务流之间没有共同可用的任务流参数/)
  assert.match(blocks, /不适用于当前函数关联的全部任务流/)
  assert.match(utils, /const BUILTIN_SHARED_VARIABLES = \[\]/)
  assert.doesNotMatch(utils, /name: 'template_state'|name: 'template_workflow_globals'/)
})
