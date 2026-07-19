import assert from 'node:assert/strict'
import test from 'node:test'

import {
  filterTaskDefinitions,
  TASK_RESOURCE_PAGE_SIZE,
} from '../src/ui/templateEditor/taskResourceList.js'
import { paginateSelectOptions } from '../src/ui/templateEditor/paginatedSelect.js'

const tasks = Array.from({ length: 10 }, (_, index) => ({
  k: `task_${index + 1}`,
  t: `任务 ${index + 1}`,
  fn: `run_${index + 1}`,
}))

test('任务管理默认按固定数量分页', () => {
  const pagination = paginateSelectOptions(tasks, 1, TASK_RESOURCE_PAGE_SIZE)

  assert.equal(pagination.options.length, 4)
  assert.equal(pagination.pageCount, 3)
  assert.equal(pagination.total, 10)
})

test('任务管理可按 Key、名称和 Blockly 函数搜索', () => {
  assert.deepEqual(filterTaskDefinitions(tasks, 'TASK_10'), [tasks[9]])
  assert.deepEqual(filterTaskDefinitions(tasks, '任务 4'), [tasks[3]])
  assert.deepEqual(filterTaskDefinitions(tasks, 'RUN_7'), [tasks[6]])
})
