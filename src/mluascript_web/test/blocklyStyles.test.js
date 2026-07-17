import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const blocklyCssUrl = new URL('../src/blockly/blockly.css', import.meta.url)
const globalCssUrl = new URL('../src/style.css', import.meta.url)

test('Blockly 样式集中在独立样式表并兼容 11/13 字段类名', async () => {
  const [blocklyCss, globalCss] = await Promise.all([
    readFile(blocklyCssUrl, 'utf8'),
    readFile(globalCssUrl, 'utf8'),
  ])

  assert.match(blocklyCss, /\.blocklyEditableField/)
  assert.match(blocklyCss, /\.blocklyEditing/)
  assert.match(blocklyCss, /\.blocklyEditableText/)
  assert.match(blocklyCss, /\.blocklyToolboxCategory/)
  assert.doesNotMatch(globalCss, /\.blockly(?:Editable|Toolbox|Tree|Path|Draggable|Scrollbar)/)
})
