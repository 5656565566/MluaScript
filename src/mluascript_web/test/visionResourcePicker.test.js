import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const srcRoot = fileURLToPath(new URL('../src/', import.meta.url))

test('vision blocks expose searchable resource pickers for template, feature and NND recognition', () => {
  const source = readFileSync(`${srcRoot}/blockly/blocks/vision.js`, 'utf8')
  const pickerSource = readFileSync(`${srcRoot}/components/PickerListContent.vue`, 'utf8')

  assert.match(source, /attachResourcePicker\(block, \{ inputName: 'TEMPLATE', title: '选择模板资源' \}\)/)
  assert.match(source, /attachResourcePicker\(block, \{ inputName: 'TEMPLATE', title: '选择特征模板资源' \}\)/)
  assert.match(source, /attachResourcePicker\(block, \{ inputName: 'MODEL', title: '选择 NND 模型资源', kind: 'model' \}\)/)
  const utilitySource = readFileSync(`${srcRoot}/blockly/utils.js`, 'utf8')
  assert.match(utilitySource, /value: `\$\{resourceKey\}:\$\{relative\}`/)
  assert.match(pickerSource, /n-pagination v-if="treeMode \? navigationNodes.length : pageItems.length"/)
  assert.match(pickerSource, /class="picker-file-browser-breadcrumb"/)
})
