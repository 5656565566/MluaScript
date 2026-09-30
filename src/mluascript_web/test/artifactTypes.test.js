import assert from 'node:assert/strict'
import test from 'node:test'

import { artifactTypeKey, artifactTypeLabel, matchesResourceQuery } from '../src/features/runtime/artifactTypes.js'

for (const [projectType, label] of [
  ['lua-package', '脚本包'],
  ['blockly-package', '脚本包'],
  ['maa', '脚本包'],
  ['lua-file', '单文件'],
  ['blockly-file', '单文件'],
]) {
  test(`shows ${projectType} as its project type`, () => {
    const artifact = { kind: 'lua', project_type: projectType }
    assert.equal(artifactTypeKey(artifact), projectType)
    assert.equal(artifactTypeLabel(artifact), label)
  })
}

test('keeps legacy artifacts readable when project_type is absent', () => {
  assert.equal(artifactTypeLabel({ kind: 'package' }), '脚本包')
  assert.equal(artifactTypeLabel({ kind: 'lua' }), '单文件')
  assert.equal(artifactTypeLabel({ kind: 'pipeline' }), '脚本包')
})

test('resource search covers package identity, version, author, path, and description', () => {
  const artifact = {
    name: '每日任务',
    path: 'scripts/daily.mlspkg',
    description: '领取奖励',
    author: 'Tester',
    version: '1.2.3',
    package_id: 'com.example.daily',
    entrypoint: 'main',
  }

  for (const query of ['每日', 'scripts/daily', '奖励', 'tester', '1.2.3', 'com.example.daily', 'main']) {
    assert.equal(matchesResourceQuery(artifact, query), true, query)
  }
  assert.equal(matchesResourceQuery(artifact, 'missing'), false)
})
