import assert from 'node:assert/strict'
import test from 'node:test'

import { artifactTypeKey, artifactTypeLabel } from '../src/features/runtime/artifactTypes.js'

for (const [projectType, label] of [
  ['lua-package', 'Lua 可打包项目'],
  ['blockly-package', 'Blockly 可打包项目'],
  ['maa', 'Maa 自动化项目'],
  ['lua-file', 'Lua 单文件'],
  ['blockly-file', 'Blockly 单文件'],
]) {
  test(`shows ${projectType} as its project type`, () => {
    const artifact = { kind: 'lua', project_type: projectType }
    assert.equal(artifactTypeKey(artifact), projectType)
    assert.equal(artifactTypeLabel(artifact), label)
  })
}

test('keeps legacy artifacts readable when project_type is absent', () => {
  assert.equal(artifactTypeLabel({ kind: 'package' }), '脚本包')
  assert.equal(artifactTypeLabel({ kind: 'lua' }), 'Lua 脚本')
})
