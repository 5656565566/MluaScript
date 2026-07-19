import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  DEFAULT_SELECT_PAGE_SIZE,
  filterSelectOptions,
  paginateSelectOptions,
} from '../src/ui/templateEditor/paginatedSelect.js'

const options = Array.from({ length: 21 }, (_, index) => ({
  label: `任务 ${index + 1}`,
  value: `task_${index + 1}`,
}))
const componentUrl = new URL('../src/ui/templateEditor/PaginatedSearchSelect.vue', import.meta.url)

test('任务选择器使用独立搜索面板和常驻分页', async () => {
  const component = await readFile(componentUrl, 'utf8')

  assert.match(component, /<n-popover/)
  assert.match(component, /width="trigger"/)
  assert.match(component, /search-placeholder|searchPlaceholder/)
  assert.match(component, /role="listbox"/)
  assert.match(component, /<n-pagination/)
  assert.match(component, /n-pagination-quick-jumper[^}]*text-align:\s*center/s)
  assert.doesNotMatch(component, /<n-select/)
})

test('任务选择器默认只返回第一页选项', () => {
  const result = paginateSelectOptions(options, 1)

  assert.equal(result.options.length, DEFAULT_SELECT_PAGE_SIZE)
  assert.equal(result.options[0].value, 'task_1')
  assert.equal(result.pageCount, 3)
  assert.equal(result.total, 21)
})

test('任务选择器分页会约束越界页码', () => {
  const result = paginateSelectOptions(options, 99)

  assert.equal(result.page, 3)
  assert.deepEqual(result.options.map(option => option.value), [
    'task_15',
    'task_16',
    'task_17',
    'task_18',
    'task_19',
    'task_20',
    'task_21',
  ])
})

test('任务选择器按名称和 Key 搜索全部选项', () => {
  assert.deepEqual(
    filterSelectOptions(options, '任务 20').map(option => option.value),
    ['task_20'],
  )
  assert.deepEqual(
    filterSelectOptions(options, 'TASK_12').map(option => option.value),
    ['task_12'],
  )
})
