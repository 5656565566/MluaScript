import test from 'node:test'
import assert from 'node:assert/strict'
import { createRuntimeActions } from '../src/features/runtime/runtimeModule.js'
import { createTemplateActions } from '../src/features/templates/templateModule.js'
import { createProjectActions } from '../src/features/projects/projectModule.js'

const ref = value => ({ value })

for (const kind of ['project', 'artifact', 'standalone']) {
  for (const fails of [false, true]) {
    test(`${kind} template submits once and reports ${fails ? 'no success on failure' : 'success once'}`, async () => {
      const notifications = []
      let requests = 0
      const state = {
        selectedTemplateMeta: ref({ type: 'task-template', tasks: [{ key: 'main' }] }),
        selectedTemplateScript: ref({ path: 'scripts/main.lua', ...(kind === 'project' ? { projectKey: 'project' } : kind === 'artifact' ? { artifactId: 'artifact' } : {}) }),
        selectedTaskKey: ref('main'), templateTaskFormData: ref({}), selectedSession: ref('ADB:selected'),
        currentProject: ref({ key: 'project', project_type: 'lua-package', primary_path: 'scripts/main.lua' }),
        projectTree: ref([{ kind: 'file', path: 'scripts/main.lua' }]),
        projectOpenFiles: ref([{ path: 'scripts/main.lua', file: { encoding: 'utf-8' }, content: 'return 42' }]),
        projectDebugLoading: ref(false), projectDebugTaskByKey: ref({}),
      }
      const failure = new Error('start failed')
      const start = async () => {
        requests += 1
        if (fails) throw failure
        return { taskId: 'task-1', message: 'started' }
      }
      let actions
      const getActions = () => actions
      actions = {
        ...createRuntimeActions({ state, systemApi: {}, runtimeStreams: {}, getActions, runApi: { runArtifact: start } }),
        ...createProjectActions({ state, getActions, projectApi: { debug: start } }),
        ...createTemplateActions({ state, getActions, projectApi: {}, artifactApi: {}, templateApi: { runWorkflow: start } }),
        saveAllProjectFiles: async () => {}, refreshTaskManagerData: async () => {}, loadState: async () => {},
        setStatus: (message, type) => notifications.push({ message, type }),
      }
      if (fails) await assert.rejects(actions.runTemplateWorkflow(), error => error === failure)
      else await actions.runTemplateWorkflow()
      assert.equal(requests, 1)
      assert.equal(notifications.length, fails ? 0 : 1)
      if (!fails) assert.equal(notifications[0].type, 'success')
    })
  }
}
