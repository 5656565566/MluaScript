import {
  buildTaskDefaults,
  buildWorkflowDefaults,
  normalizeTemplateMeta,
  normalizeTemplateSavedConfig,
} from './templateDomain.js'

export function createTemplateActions({ state, templateApi, projectApi, artifactApi, getActions }) {
  function applyTemplateState(meta, savedConfig, readme = null) {
    state.selectedTemplateMeta.value = meta
    state.templateReadme.value = readme
    state.templateRunnerTab.value = readme ? '__readme__' : ''
    if (meta?.type === 'workflow-template') {
      state.templateScriptType.value = 'workflow-template'
      state.selectedWorkflowKey.value = savedConfig?.selectedFlowKey || meta.entry?.defaultWorkflow || meta.workflows?.[0]?.key || ''
      state.templateWorkflowFormData.value = buildWorkflowDefaults(meta, savedConfig)
      return
    }
    state.templateScriptType.value = 'task-template'
    state.selectedWorkflowKey.value = ''
    state.templateTaskFormData.value = buildTaskDefaults(meta, savedConfig)
    state.templateWorkflowFormData.value = {}
  }

  return {
    async loadTemplate(scriptPath) {
      const data = await templateApi.getScriptTemplate(scriptPath)
      const payload = data.data || data
      if (!payload.hasTemplate) {
        state.selectedTemplateMeta.value = null
        state.selectedTemplateSavedConfig.value = {}
        state.selectedTemplateScript.value = scriptPath
        state.selectedTemplateConfigPath.value = ''
        state.templateScriptType.value = ''
        state.selectedWorkflowKey.value = ''
        state.templateTaskFormData.value = {}
        state.templateWorkflowFormData.value = {}
        state.templateReadme.value = null
        state.templateRunnerTab.value = ''
        return payload
      }

      const meta = normalizeTemplateMeta(payload.meta)
      const savedConfig = normalizeTemplateSavedConfig(payload.savedConfig)
      state.selectedTemplateScript.value = {
        path: payload.scriptPath || scriptPath,
        name: payload.scriptName || String(payload.scriptPath || scriptPath).split('/').pop() || String(scriptPath).split('/').pop() || '模板脚本',
      }
      state.selectedTemplateConfigPath.value = payload.configPath || ''
      state.selectedTemplateSavedConfig.value = savedConfig
      applyTemplateState(meta, savedConfig, payload.readme || null)
      return payload
    },

    async loadProjectTemplate(projectKey, entryPath, snapshot = null) {
      const payload = snapshot
        ? await projectApi.previewTemplate(projectKey, snapshot)
        : await projectApi.getTemplate(projectKey, entryPath)
      if (!payload.hasTemplate) throw new Error('当前脚本没有模板元数据')
      const meta = normalizeTemplateMeta(payload.meta)
      const savedConfig = normalizeTemplateSavedConfig(payload.savedConfig)
      state.selectedTemplateScript.value = {
        path: payload.scriptPath || entryPath,
        name: String(payload.scriptPath || entryPath).split('/').pop() || '模板脚本',
        projectKey,
        entryPath: payload.scriptPath || entryPath,
      }
      state.selectedTemplateConfigPath.value = payload.configPath || ''
      state.selectedTemplateSavedConfig.value = savedConfig
      applyTemplateState(meta, savedConfig, payload.readme || null)
      return payload
    },

    async loadArtifactTemplate(artifactId) {
      if (!artifactApi?.getArtifactTemplate) throw new Error('构建包模板接口不可用')
      const response = await artifactApi.getArtifactTemplate(artifactId)
      const payload = response.data || response
      if (!payload.hasTemplate) throw new Error('构建入口没有模板元数据')
      const meta = normalizeTemplateMeta(payload.meta)
      const savedConfig = normalizeTemplateSavedConfig(payload.savedConfig)
      state.selectedTemplateScript.value = {
        path: payload.scriptPath || '',
        name: payload.name || String(payload.scriptPath || '').split('/').pop() || '模板脚本',
        artifactId,
        entryPath: payload.scriptPath || '',
      }
      state.selectedTemplateConfigPath.value = payload.configPath || ''
      state.selectedTemplateSavedConfig.value = savedConfig
      applyTemplateState(meta, savedConfig, payload.readme || null)
      return payload
    },

    setTemplateSelectedFlow(key) {
      state.selectedWorkflowKey.value = key || ''
    },

    setTemplateCurrentStep(key) {
      state.selectedTaskKey.value = key || ''
    },

    updateTemplateTaskValue(taskKey, fieldKey, value) {
      state.templateTaskFormData.value = {
        ...state.templateTaskFormData.value,
        [taskKey]: {
          ...(state.templateTaskFormData.value[taskKey] || {}),
          [fieldKey]: value,
        },
      }
    },

    updateWorkflowGlobals(workflowKey, globals) {
      if (!workflowKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
      state.templateWorkflowFormData.value = {
        ...state.templateWorkflowFormData.value,
        [workflowKey]: {
          ...state.templateWorkflowFormData.value[workflowKey],
          globals: { ...(globals || {}) },
        },
      }
    },

    updateWorkflowStepArg(workflowKey, stepKey, fieldKey, value) {
      if (!workflowKey || !stepKey || !fieldKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
      const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
      state.templateWorkflowFormData.value = {
        ...state.templateWorkflowFormData.value,
        [workflowKey]: {
          ...currentWorkflow,
          stepArgs: {
            ...(currentWorkflow.stepArgs || {}),
            [stepKey]: {
              ...(currentWorkflow.stepArgs?.[stepKey] || {}),
              [fieldKey]: value,
            },
          },
        },
      }
    },

    updateWorkflowStepEnabled(workflowKey, stepKey, enabled) {
      if (!workflowKey || !stepKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
      const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
      state.templateWorkflowFormData.value = {
        ...state.templateWorkflowFormData.value,
        [workflowKey]: {
          ...currentWorkflow,
          stepEnabled: {
            ...(currentWorkflow.stepEnabled || {}),
            [stepKey]: Boolean(enabled),
          },
        },
      }
    },

    moveWorkflowStep(workflowKey, stepKey, direction) {
      if (!workflowKey || !stepKey || !state.templateWorkflowFormData.value?.[workflowKey]) return
      const currentWorkflow = state.templateWorkflowFormData.value[workflowKey]
      const list = Array.isArray(currentWorkflow.stepOrder) ? [...currentWorkflow.stepOrder] : []
      const index = list.indexOf(stepKey)
      if (index < 0) return
      const target = direction === 'up' ? index - 1 : index + 1
      if (target < 0 || target >= list.length) return
      const [item] = list.splice(index, 1)
      list.splice(target, 0, item)
      state.templateWorkflowFormData.value = {
        ...state.templateWorkflowFormData.value,
        [workflowKey]: { ...currentWorkflow, stepOrder: list },
      }
    },

    buildTemplateRunPayload() {
      const meta = state.selectedTemplateMeta.value
      if (!meta) throw new Error('当前没有模板元数据')
      const script = state.selectedTemplateScript.value
      const scriptPath = typeof script === 'string' ? script : script?.path
      if (!scriptPath) throw new Error('缺少模板脚本路径')
      if (meta.type === 'workflow-template') {
        const workflowKey = state.selectedWorkflowKey.value || meta.entry?.defaultWorkflow || meta.workflows?.[0]?.key || ''
        if (!workflowKey) throw new Error('缺少工作流选择')
        return {
          scriptPath,
          mode: 'workflow',
          workflowKey,
          workflow: state.templateWorkflowFormData.value?.[workflowKey] || {},
          runtime: {},
        }
      }
      return {
        scriptPath,
        mode: 'task',
        workflowKey: '',
        workflow: {},
        runtime: {
          selectedTaskKey: state.selectedTaskKey.value || meta.entry?.defaultTask || meta.tasks?.[0]?.key || '',
          tasks: state.templateTaskFormData.value,
        },
      }
    },

    async runTemplateWorkflow() {
      const actions = getActions()
      const payload = actions.buildTemplateRunPayload()
      const script = state.selectedTemplateScript.value
      const data = script?.projectKey
        ? await actions.debugProject({
            mode: 'template',
            entryPath: script.entryPath || script.path,
            templatePayload: payload,
          })
        : script?.artifactId
          ? await actions.runArtifactTemplate(script.artifactId, payload)
        : await templateApi.runWorkflow(payload)
      await actions.loadState()
      actions.setStatus(data.message || '模板任务已启动', 'success')
      return data
    },

    async openTemplateEditor(meta = null, callback = null) {
      state.templateEditorModalVisible.value = true
      state.templateEditorModalData.value = meta
      state.templateEditorModalCallback.value = callback
    },

    async closeTemplateEditor() {
      state.templateEditorModalVisible.value = false
      state.templateEditorModalData.value = null
      state.templateEditorModalCallback.value = null
    },

    async saveTemplateEditorMeta(meta) {
      if (typeof state.templateEditorModalCallback.value === 'function') {
        await state.templateEditorModalCallback.value(meta)
      }
    },
  }
}

