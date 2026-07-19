import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const shellUrl = new URL('../src/components/PickerModalShell.vue', import.meta.url)
const shellStyleUrl = new URL('../src/components/pickerModalShell.css', import.meta.url)
const listUrl = new URL('../src/components/PickerListContent.vue', import.meta.url)
const listStyleUrl = new URL('../src/components/pickerListContent.css', import.meta.url)

test('选择器只滚动列表并固定底部操作区', async () => {
  const [shell, shellStyle, list, listStyle] = await Promise.all([
    readFile(shellUrl, 'utf8'),
    readFile(shellStyleUrl, 'utf8'),
    readFile(listUrl, 'utf8'),
    readFile(listStyleUrl, 'utf8'),
  ])

  assert.match(shell, /class="picker-modal-shell"[\s\S]*class="picker-modal-body"[\s\S]*class="picker-modal-footer"/)
  assert.match(shellStyle, /\.picker-modal-footer\s*\{[^}]*flex:\s*none/s)
  assert.match(shellStyle, /\.picker-modal-body\s*\{[^}]*flex:\s*1[^}]*overflow:\s*hidden/s)
  assert.match(shellStyle, /:global\(\.picker-modal-panel > \.n-card-content\)\s*\{[^}]*display:\s*flex[^}]*overflow:\s*hidden !important/s)
  assert.match(shellStyle, /:global\(\.picker-modal-content-wrap\)\s*\{[^}]*flex:\s*1[^}]*height:\s*auto !important/s)
  assert.match(list, /class="picker-list-content"[\s\S]*class="picker-list-scroll"/)
  assert.match(listStyle, /\.picker-list-scroll\s*\{[^}]*flex:\s*1[^}]*min-height:\s*0[^}]*overflow-y:\s*auto/s)
})
