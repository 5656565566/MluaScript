import {
  buildTaskDefaults,
  buildWorkflowDefaults,
  normalizeTemplateMeta,
  normalizeTemplateSavedConfig,
} from './templateDomain'

export function createTemplateActions({ state, templateApi, getActions }) {
  function applyTemplateState(meta, savedConfig) {
    state.selectedTemplateMeta.value = meta
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
      applyTemplateState(meta, savedConfig)
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
        runtime: { tasks: state.templateTaskFormData.value },
      }
    },

    async runTemplateWorkflow() {
      const actions = getActions()
      const data = await templateApi.runWorkflow(actions.buildTemplateRunPayload())
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
      await getActions().closeTemplateEditor()
    },
  }
}

