import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const fieldsUrl = new URL('../src/blockly/fields.js', import.meta.url)

test('Blockly 字段编辑器保留 WidgetDiv 的 DOM 所有权', async () => {
  const source = await readFile(fieldsUrl, 'utf8')

  assert.doesNotMatch(source, /\.prototype\.showEditor_\s*=/)
  assert.doesNotMatch(source, /\.prototype\.widgetDispose_\s*=/)
  assert.doesNotMatch(source, /appendChild\(instance\.htmlInput_\)/)
  assert.doesNotMatch(source, /WidgetDiv\.getDiv\(\)/)
})
