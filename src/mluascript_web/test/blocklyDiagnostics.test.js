import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'

const generatorUrl = new URL('../src/blockly/generator.js', import.meta.url)
const editorUrl = new URL('../src/features/editor/editorModule.js', import.meta.url)
const managerUrl = new URL('../src/components/BlocklyWorkspaceManagerModal.vue', import.meta.url)

test('Blockly 诊断包含积木警告和失效变量', async () => {
  const source = await readFile(generatorUrl, 'utf8')
  assert.match(source, /export function collectBlocklyDiagnostics/)
  assert.match(source, /getWarningText/)
  assert.match(source, /isInvalidVariableBlock\(block\)/)
})

test('保存和直接执行当前 Blockly 前都会阻止语义错误', async () => {
  const [editor, manager] = await Promise.all([
    readFile(editorUrl, 'utf8'),
    readFile(managerUrl, 'utf8'),
  ])
  assert.match(editor, /async saveLuaScript\(\)\s*\{[\s\S]*?assertBlocklyLuaReady\(\)/)
  assert.match(editor, /async runCurrentBlocklyLua\(\)\s*\{[\s\S]*?assertBlocklyLuaReady\(\)/)
  assert.match(manager, /actions\.handleAction\(actions\.runCurrentBlocklyLua\)/)
})

test('Lua 生成异常会保留为编辑器错误，且保存使用幂等更新接口', async () => {
  const [editor, generator] = await Promise.all([
    readFile(editorUrl, 'utf8'),
    readFile(generatorUrl, 'utf8'),
  ])

  assert.match(editor, /blocklyGenerationError\.value = message/)
  assert.match(editor, /const data = await editorApi\.updateLuaFile\(payload\)/)
  assert.doesNotMatch(editor, /hasPersistedFile\s*\?\s*await editorApi\.updateLuaFile/)
  assert.equal((generator.match(/luaGenerator\.workspaceToCode\(workspace\)/g) || []).length, 1)
  assert.match(generator, /throw new Error\(`生成 Lua 代码失败：/)
})
