import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { createTemplateActions } from '../src/features/templates/templateModule.js'

test('自动保存模板数据时不会关闭编辑器', async () => {
  const saved = []
  let closeCount = 0
  const actions = createTemplateActions({
    state: {
      templateEditorModalCallback: ref(payload => saved.push(payload)),
    },
    templateApi: {},
    getActions: () => ({
      closeTemplateEditor() {
        closeCount += 1
      },
    }),
  })

  await actions.saveTemplateEditorMeta({ id: 'autosave_demo' })

  assert.deepEqual(saved, [{ id: 'autosave_demo' }])
  assert.equal(closeCount, 0)
})
