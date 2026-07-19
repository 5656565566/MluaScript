import assert from 'node:assert/strict'
import test from 'node:test'
import { nextTick, ref } from 'vue'

import { useTemplateEditor } from '../src/ui/templateEditor/useTemplateEditor.js'

test('模板编辑器公开刷新 Blockly 函数列表的方法', () => {
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(false),
      templateEditorModalData: ref({}),
    },
    message: {
      success() {},
      warning() {},
    },
    getProcedureDefinitions: () => [{
      name: 'run',
      hasReturn: false,
      block: {
        getProcedureDef: () => ['run', ['args'], false],
      },
    }],
    closeEditor() {},
    saveEditorMeta() {},
  })

  assert.equal(typeof editor.refreshProcedureDefinitions, 'function')
  editor.refreshProcedureDefinitions()
  assert.deepEqual(editor.procedureOptions.value, [{
    label: 'run(args)',
    value: 'run',
  }])
})

test('关闭模板编辑器前会刷新最后一次自动保存', async () => {
  const saved = []
  let closed = false
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(true),
      templateEditorModalData: ref({ id: 'autosave_demo' }),
    },
    message: { warning() {} },
    getProcedureDefinitions: () => [],
    closeEditor() {
      closed = true
    },
    saveEditorMeta(payload) {
      saved.push(payload)
    },
  })

  await nextTick()
  editor.localData.value.t = '自动保存标题'
  await nextTick()
  await editor.handleClose()

  assert.equal(saved.at(-1).t, '自动保存标题')
  assert.equal(editor.autosaveStatus.value, 'saved')
  assert.equal(closed, true)
})
