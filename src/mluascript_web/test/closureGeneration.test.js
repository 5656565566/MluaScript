import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'

const variableContextUrl = new URL('../src/blockly/variableContext.js', import.meta.url)
const generatorUrl = new URL('../src/blockly/generator.js', import.meta.url)

test('named functions can select only lexically preceding workspace locals', async () => {
  const source = await readFile(variableContextUrl, 'utf8')

  assert.match(source, /function getCapturableWorkspaceLocalVariables/)
  assert.match(source, /getBranchPath\(candidate\)\.length === 0/)
  assert.match(source, /isReachableBefore\(candidate, procedureBlock\)/)
  assert.match(source, /!argumentNames\.has/)
  assert.match(source, /sort\(\(a, b\) => getBlockY\(b\) - getBlockY\(a\)\)/)
  assert.match(source, /kind: 'closure'/)
  assert.match(source, /外层局部变量/)
})

test('capturing functions remain after the outer local declaration', async () => {
  const source = await readFile(generatorUrl, 'utf8')

  assert.match(source, /getProcedureClosureCaptures\(block\)/)
  assert.match(source, /const definitionKey = `%\$\{functionName\}`/)
  assert.match(source, /delete generator\.definitions_\[definitionKey\]/)
  assert.match(source, /return `\$\{definition\}\\n`/)
})
