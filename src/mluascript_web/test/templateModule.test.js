import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

import { createTemplateActions } from '../src/features/templates/templateModule.js'

function templateState() {
  return Object.fromEntries([
    'selectedTemplateMeta',
    'selectedTemplateSavedConfig',
    'selectedTemplateScript',
    'selectedTemplateConfigPath',
    'templateScriptType',
    'selectedWorkflowKey',
    'templateTaskFormData',
    'templateWorkflowFormData',
    'templateReadme',
    'templateRunnerTab',
    'selectedTaskKey',
  ].map(key => [key, ref(key.includes('FormData') ? {} : '')]))
}

test('project templates open their README as the first non-runtime tab', async () => {
  const state = templateState()
  const actions = createTemplateActions({
    state,
    templateApi: {},
    projectApi: {
      async getTemplate() {
        return {
          hasTemplate: true,
          scriptPath: 'scripts/main.lua',
          configPath: 'settings/main.yaml',
          meta: {
            mode: 'wf',
            tasks: [{ k: 'task', fn: 'run_task' }],
            flows: [{ k: 'main', steps: [{ k: 'step', task: 'task' }] }],
          },
          savedConfig: {},
          readme: { path: 'README.md', markdown: '# Demo\n' },
        }
      },
    },
    getActions: () => actions,
  })

  await actions.loadProjectTemplate('project-key', 'scripts/main.lua')

  assert.equal(state.templateReadme.value.markdown, '# Demo\n')
  assert.equal(state.templateRunnerTab.value, '__readme__')
  assert.equal(state.selectedWorkflowKey.value, 'main')
})

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
