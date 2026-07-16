<script setup>
import { computed, watch, h } from 'vue'
import { state, actions } from '../store'
import {
  NCard,
  NSpace,
  NButton,
  NEmpty,
  NTabs,
  NTabPane,
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NLayout,
  NLayoutSider,
  NLayoutContent,
  NList,
  NListItem,
  NThing,
  NText,
  NIcon,
} from 'naive-ui'

const templateTitle = computed(() => state.selectedTemplateMeta.value?.userTitle || state.selectedTemplateMeta.value?.title || state.selectedTemplateScript.value?.name || '模板执行')
const isWorkflow = computed(() => state.templateScriptType.value === 'workflow-template')
const workflows = computed(() => state.selectedTemplateMeta.value?.workflows || [])
const currentWorkflow = computed(() => workflows.value.find(item => item.key === state.selectedWorkflowKey.value) || workflows.value[0] || null)

const currentWorkflowState = computed(() => {
  const workflowKey = currentWorkflow.value?.key
  if (!workflowKey) return { stepArgs: {}, stepEnabled: {}, stepOrder: [], globals: {} }
  return state.templateWorkflowFormData.value[workflowKey] || { stepArgs: {}, stepEnabled: {}, stepOrder: [], globals: {} }
})

const orderedWorkflowTasks = computed(() => {
  const workflow = currentWorkflow.value
  if (!workflow) return []
  const order = currentWorkflowState.value.stepOrder || []
  const tasksByKey = Object.fromEntries((workflow.tasks || []).map(task => [task.key, task]))
  const result = []
  const seen = new Set()
  for (const taskKey of order) {
    const task = tasksByKey[taskKey]
    if (task) {
      result.push(task)
      seen.add(taskKey)
    }
  }
  for (const task of workflow.tasks || []) {
    if (!seen.has(task.key)) result.push(task)
  }
  return result
})

const selectedStepKey = computed({
  get: () => state.selectedWorkflowStepKey.value,
  set: value => { state.selectedWorkflowStepKey.value = value },
})
const currentStep = computed(() => selectedStepKey.value ? orderedWorkflowTasks.value.find(item => item.key === selectedStepKey.value) || null : null)

watch(currentWorkflow, () => {
  const ordered = orderedWorkflowTasks.value
  if (!ordered.length) {
    selectedStepKey.value = ''
    return
  }
  if (!selectedStepKey.value || !ordered.some(step => step.key === selectedStepKey.value)) {
    selectedStepKey.value = ordered[0].key
  }
}, { immediate: true })

function selectStep(stepKey) {
  selectedStepKey.value = stepKey
}

function normalizeFieldOptions(field) {
  const rawOptions = field?.options || field?.cases || field?.oneOf || []
  if (!Array.isArray(rawOptions)) return []
  return rawOptions.map((option) => {
    if (option && typeof option === 'object') {
      const value = option.value ?? option.v ?? option.name ?? option.key ?? ''
      return {
        value,
        label: option.label ?? option.t ?? option.title ?? String(value),
      }
    }
    return {
      value: option,
      label: String(option),
    }
  })
}

function fieldDefaultValue(field) {
  if (Object.prototype.hasOwnProperty.call(field || {}, 'default')) return field.default
  if (Object.prototype.hasOwnProperty.call(field || {}, 'def')) return field.def
  if (field?.type === 'boolean') return false
  return ''
}

function fieldDisplayValue(field, value) {
  if (['json', 'obj', 'list'].includes(field?.type)) {
    if (typeof value === 'string') return value
    return JSON.stringify(value ?? fieldDefaultValue(field), null, 2)
  }
  return value ?? fieldDefaultValue(field)
}

function getWorkflowState() {
  return currentWorkflowState.value || { stepArgs: {}, stepEnabled: {}, stepOrder: [], globals: {} }
}

function getGlobalFieldByKey(key) {
  if (!key) return null
  return (currentWorkflow.value?.globals || []).find(field => field.key === key) || state.selectedTemplateMeta.value?.vars?.[key] || null
}

function getStepFieldByKey(stepKey, key) {
  if (!stepKey || !key) return null
  const step = (currentWorkflow.value?.tasks || []).find(item => item.key === stepKey)
  return (step?.fields || []).find(field => field.key === key) || state.selectedTemplateMeta.value?.vars?.[key] || null
}

function getGlobalValueByKey(key) {
  const field = getGlobalFieldByKey(key) || { key }
  const globals = getWorkflowState().globals || {}
  return Object.prototype.hasOwnProperty.call(globals, key) ? globals[key] : fieldDefaultValue(field)
}

function getStepValueByKey(stepKey, key) {
  const field = getStepFieldByKey(stepKey, key) || { key }
  const stepArgs = getWorkflowState().stepArgs?.[stepKey] || {}
  return Object.prototype.hasOwnProperty.call(stepArgs, key) ? stepArgs[key] : fieldDefaultValue(field)
}

function getDependencyValue(conditionKey, stepKey = '') {
  if (stepKey) {
    const step = (currentWorkflow.value?.tasks || []).find(item => item.key === stepKey)
    const inStep = (step?.fields || []).some(field => field.key === conditionKey)
    if (inStep) return getStepValueByKey(stepKey, conditionKey)
  }
  return getGlobalValueByKey(conditionKey)
}

function isConditionActive(field, stepKey = '') {
  const condition = field?.if
  if (!condition?.k) return true
  const currentValue = getDependencyValue(condition.k, stepKey)
  if (Array.isArray(condition.in) && condition.in.length) return condition.in.includes(currentValue)
  if (Object.prototype.hasOwnProperty.call(condition, 'ne')) return currentValue !== condition.ne
  if (Object.prototype.hasOwnProperty.call(condition, 'eq')) return currentValue === condition.eq
  return Boolean(currentValue)
}

function workflowFieldModel(stepKey, field) {
  return getStepValueByKey(stepKey, field.key)
}

function updateWorkflowField(stepKey, field, value) {
  const workflowKey = currentWorkflow.value?.key
  if (!workflowKey) return
  actions.updateWorkflowStepArg(workflowKey, stepKey, field.key, value)
}

function isStepEnabled(stepKey) {
  return Boolean(getWorkflowState().stepEnabled?.[stepKey] ?? true)
}

function setStepEnabled(stepKey, enabled) {
  const workflowKey = currentWorkflow.value?.key
  if (!workflowKey) return
  actions.updateWorkflowStepEnabled(workflowKey, stepKey, enabled)
}

function moveStep(stepKey, direction) {
  const workflowKey = currentWorkflow.value?.key
  if (!workflowKey) return
  actions.moveWorkflowStep(workflowKey, stepKey, direction)
}

function workflowGlobalValue(field) {
  return getGlobalValueByKey(field.key)
}

function visibleWorkflowGlobals() {
  return (currentWorkflow.value?.globals || []).filter(field => isConditionActive(field))
}

function updateWorkflowGlobal(field, value) {
  const workflowKey = currentWorkflow.value?.key
  if (!workflowKey) return
  const current = getWorkflowState()
  actions.updateWorkflowGlobals(workflowKey, {
    ...(current.globals || {}),
    [field.key]: value,
  })
}

function groupedFields(fields) {
  const visible = (fields || []).filter(field => isConditionActive(field, currentStep.value?.key || ''))
  const indexMap = new Map(visible.map((field, index) => [field.key, index]))
  return [...visible].sort((a, b) => {
    if (a.grp && a.grp === b.key) return 1
    if (b.grp && b.grp === a.key) return -1
    return (indexMap.get(a.key) ?? 0) - (indexMap.get(b.key) ?? 0)
  })
}

function groupedStepFields(step) {
  return groupedFields(step?.fields || [])
}

function fieldItemStyle(field) {
  return field.grp
    ? 'margin-bottom: 18px; padding-left: 18px; border-left: 2px solid var(--n-border-color);'
    : 'margin-bottom: 18px;'
}

function openFromScriptManager() {
  state.activeView.value = 'task-manager'
}

function renderFieldControl(field, value, onUpdate) {
  if (field.type === 'number') {
    return h(NInputNumber, {
      value,
      'onUpdate:value': onUpdate,
      min: field.min,
      max: field.max,
      placeholder: field.description || '请输入数字',
      clearable: true,
      style: { width: '100%' },
    })
  }
  if (field.type === 'select') {
    return h(NSelect, {
      value,
      'onUpdate:value': onUpdate,
      options: normalizeFieldOptions(field),
      style: { width: '100%' },
    })
  }
  if (field.type === 'boolean') {
    return h(NSwitch, {
      value: Boolean(value),
      'onUpdate:value': onUpdate,
    })
  }
  if (['json', 'obj', 'list'].includes(field.type)) {
    return h(NInput, {
      type: 'textarea',
      value: fieldDisplayValue(field, value),
      'onUpdate:value': onUpdate,
      placeholder: field.description || '请输入 JSON 数据',
      rows: 4,
      style: { fontFamily: 'monospace', width: '100%' },
    })
  }
  return h(NInput, {
    value,
    'onUpdate:value': onUpdate,
    placeholder: field.description || '请输入...',
    clearable: true,
    style: { width: '100%' },
  })
}
</script>

<template>
  <n-card class="template-runner-view" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;" content-style="display: flex; flex-direction: column; padding: 0 16px 16px; flex: 1; min-height: 0;" footer-style="padding: 12px 16px;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span>{{ templateTitle }}</span>
        <n-space>
          <n-button size="small" @click="openFromScriptManager">返回脚本管理</n-button>
          <n-button
            v-if="isWorkflow"
            type="primary"
            size="small"
            :disabled="state.loading.value || !state.selectedTemplateScript.value || !currentWorkflow"
            @click="actions.handleAction(() => actions.runTemplateWorkflow())"
          >执行工作流</n-button>
        </n-space>
      </div>
    </template>

    <div style="flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
      <n-empty v-if="!state.selectedTemplateScript.value" description="请先在脚本管理中选择一个模板脚本" style="margin: auto;" />

      <template v-else-if="isWorkflow">
        <n-tabs v-if="workflows.length > 1" v-model:value="state.selectedWorkflowKey.value" type="line" size="small" style="flex-shrink: 0;">
          <n-tab-pane v-for="workflow in workflows" :key="workflow.key" :name="workflow.key" :tab="workflow.userTitle || workflow.title || workflow.key" />
        </n-tabs>

        <div v-if="currentWorkflow" class="template-runner-shell">
          <div style="flex-shrink: 0;">
            <n-text style="font-size: 16px; font-weight: bold;">{{ currentWorkflow.userTitle || currentWorkflow.title || currentWorkflow.key }}</n-text>
            <p v-if="currentWorkflow.userDescription || currentWorkflow.description" style="margin: 4px 0 0; color: var(--n-text-color-3); font-size: 13px;">
              {{ currentWorkflow.userDescription || currentWorkflow.description }}
            </p>
          </div>

          <n-collapse v-if="visibleWorkflowGlobals().length" style="background: var(--n-color-embedded); padding: 0 16px; border-radius: 4px; border: 1px solid var(--n-border-color); flex-shrink: 0;">
            <n-collapse-item title="全局变量" name="globals" style="margin: 0;">
              <n-form label-placement="top" :show-feedback="false" style="margin-top: 8px;">
                <n-form-item v-for="field in visibleWorkflowGlobals()" :key="field.key" :label="field.label || field.key" :style="fieldItemStyle(field)">
                  <template #label v-if="field.description">
                    <n-text>{{ field.label || field.key }}</n-text>
                    <n-text depth="3" style="font-size: 12px; margin-left: 8px;">{{ field.description }}</n-text>
                  </template>
                  <component :is="renderFieldControl(field, workflowGlobalValue(field), val => updateWorkflowGlobal(field, val))" />
                </n-form-item>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <div class="template-content-grid">
            <div class="template-step-list-panel">
              <n-list hoverable clickable class="template-step-list">
                <n-list-item
                  v-for="step in orderedWorkflowTasks"
                  :key="step.key"
                  @click="selectStep(step.key)"
                  class="step-item"
                  :class="{ active: selectedStepKey === step.key }"
                >
                  <n-thing>
                    <template #header>
                      <n-text :depth="isStepEnabled(step.key) ? 1 : 3">{{ step.userTitle || step.title || step.key }}</n-text>
                    </template>
                    <template #description v-if="step.userDescription || step.description">
                      <n-text depth="3" style="font-size: 12px;">{{ step.userDescription || step.description }}</n-text>
                    </template>
                  </n-thing>
                  <template #suffix>
                    <n-space align="center" :wrap="false" @click.stop>
                      <n-space :size="2" vertical v-if="step.allowReorder !== false">
                        <n-button size="tiny" quaternary @click="moveStep(step.key, 'up')">
                          <template #icon><n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M18 15l-6-6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></n-icon></template>
                        </n-button>
                        <n-button size="tiny" quaternary @click="moveStep(step.key, 'down')">
                          <template #icon><n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></n-icon></template>
                        </n-button>
                      </n-space>
                      <n-switch v-if="step.allowDisable !== false" :value="isStepEnabled(step.key)" @update:value="setStepEnabled(step.key, $event)" size="small" />
                    </n-space>
                  </template>
                </n-list-item>
              </n-list>
            </div>

            <div class="template-step-detail-panel">
              <div v-if="currentStep" class="template-step-detail-scroll">
                <div style="margin-bottom: 24px;">
                  <n-text style="font-size: 18px; font-weight: bold;">{{ currentStep.userTitle || currentStep.title || currentStep.key }}</n-text>
                  <n-text v-if="currentStep.userDescription || currentStep.description" depth="3" style="display: block; margin-top: 12px; font-size: 13px;">
                    {{ currentStep.userDescription || currentStep.description }}
                  </n-text>
                </div>

                <n-form v-if="groupedStepFields(currentStep).length" label-placement="top" :show-feedback="false" class="template-step-form">
                  <n-form-item v-for="field in groupedStepFields(currentStep)" :key="`${currentStep.key}-${field.key}`" :label="field.label || field.key" :style="fieldItemStyle(field)">
                    <template #label v-if="field.description">
                      <n-text>{{ field.label || field.key }}</n-text>
                      <n-text depth="3" style="font-size: 12px; margin-left: 8px;">{{ field.description }}</n-text>
                    </template>
                    <component :is="renderFieldControl(field, workflowFieldModel(currentStep.key, field), val => updateWorkflowField(currentStep.key, field, val))" />
                  </n-form-item>
                </n-form>
                <n-empty v-else description="该任务未定义配置字段" style="margin-top: 40px;" />
              </div>
              <n-empty v-else description="请在左侧选择一个任务步骤进行设置" style="margin: auto;" />
            </div>
          </div>
        </div>
      </template>

    </div>

    <template #footer v-if="state.selectedTemplateScript.value">
      <n-collapse class="template-footer-meta" style="background: var(--n-color-embedded); padding: 0 16px; border-radius: 4px; border: 1px solid var(--n-border-color); margin: 0;">
        <n-collapse-item title="脚本信息" name="script-info" style="margin: 0;">
          <div style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 8px; font-size: 12px;">
            <div class="template-meta-row">
              <n-text depth="3">脚本：</n-text>
              <n-text>{{ state.selectedTemplateScript.value.name }}</n-text>
            </div>
            <div class="template-meta-row">
              <n-text depth="3">路径：</n-text>
              <n-text class="template-meta-code" depth="2">{{ state.selectedTemplateScript.value.path }}</n-text>
            </div>
            <div v-if="state.selectedTemplateConfigPath.value" class="template-meta-row">
              <n-text depth="3">配置：</n-text>
              <n-text class="template-meta-code" depth="2">{{ state.selectedTemplateConfigPath.value }}</n-text>
            </div>
          </div>
        </n-collapse-item>
      </n-collapse>
    </template>
  </n-card>
</template>

<style scoped>
.template-runner-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.template-runner-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-top: 12px;
  gap: 12px;
}

.template-content-grid {
  flex: 1;
  min-height: 0;
  min-width: 0;
  display: flex;
  gap: 12px;
}

.template-step-list-panel {
  width: 320px;
  flex-shrink: 0;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  background: var(--n-color);
  display: flex;
  flex-direction: column;
}

.template-step-list {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
}

.step-item {
  border-left: 4px solid transparent !important;
  transition: background-color 0.2s, border-color 0.2s;
}

.step-item:hover {
  background-color: var(--n-color-active) !important;
}

.step-item.active {
  background-color: color-mix(in srgb, var(--n-primary-color) 10%, transparent) !important;
  border-left-color: var(--n-primary-color) !important;
}

.template-step-detail-panel {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  background: var(--n-color);
  display: flex;
  flex-direction: column;
}

.template-step-detail-scroll {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  padding: 24px;
  box-sizing: border-box;
}

.template-step-form {
  max-width: 720px;
}

.template-meta-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.template-meta-code {
  font-family: monospace;
  word-break: break-all;
}

@media (max-width: 960px) {
  .template-content-grid {
    flex-direction: column;
  }
  .template-step-list-panel {
    width: auto;
    flex: 0 0 38%;
    min-height: 220px;
  }
}
</style>
