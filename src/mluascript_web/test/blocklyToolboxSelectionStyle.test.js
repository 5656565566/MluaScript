import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const cssUrl = new URL('../src/blockly/blockly.css', import.meta.url)

test('Blockly 工具箱分类保留原生选中样式', async () => {
  const source = await readFile(cssUrl, 'utf8')

  assert.match(source, /\.blocklyToolboxCategory\.blocklyToolboxSelected\s+\.blocklyToolboxCategoryLabel\s*\{[^}]*color:\s*var\(--blockly-toolbox-selected-text\)\s*!important/s)
  assert.doesNotMatch(source, /\.blocklyToolboxCategory\.blocklyToolboxSelected\s*\{[^}]*(?:background|box-shadow|font-weight)/s)
})
