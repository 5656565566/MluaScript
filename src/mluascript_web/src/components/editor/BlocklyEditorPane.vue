<script setup>
import { nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import * as Blockly from 'blockly'
import { state } from '../../store'
import {
  collectBlocklyDiagnostics,
  createBlocklyWorkspace,
  workspaceToLua,
  workspaceToXml,
} from '../../blockly'
import { replaceBlocklyWorkspace } from '../../features/editor/blocklyWorkspace'

const props = defineProps({
  modelValue: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'generated', 'save'])
const hostRef = shallowRef(null)
const workspaceRef = shallowRef(null)
let resizeObserver = null
let changeTimer = null
let lastEmittedXml = ''
let lastSuccessfulLua = ''

function resizeWorkspace() {
  window.requestAnimationFrame(() => {
    if (workspaceRef.value) Blockly.svgResize(workspaceRef.value)
  })
}

function generatePreview() {
  const workspace = workspaceRef.value
  if (!workspace) return null
  const diagnostics = collectBlocklyDiagnostics(workspace)
  try {
    lastSuccessfulLua = workspaceToLua(workspace)
    emit('generated', lastSuccessfulLua, diagnostics, false)
    return { code: lastSuccessfulLua, diagnostics, stale: false }
  } catch (error) {
    const failedDiagnostics = [
      ...diagnostics,
      { severity: 'error', message: error?.message || 'Lua 生成失败' },
    ]
    emit('generated', lastSuccessfulLua, failedDiagnostics, true)
    return { code: lastSuccessfulLua, diagnostics: failedDiagnostics, stale: true }
  }
}

defineExpose({ compile: generatePreview })

function flushWorkspaceChange() {
  generatePreview()
}

function scheduleWorkspaceChange(event) {
  if (event?.isUiEvent || event?.type === Blockly.Events.FINISHED_LOADING) return
  const xml = workspaceToXml(workspaceRef.value)
  if (xml !== props.modelValue) {
    lastEmittedXml = xml
    emit('update:modelValue', xml)
  }
  if (changeTimer) window.clearTimeout(changeTimer)
  changeTimer = window.setTimeout(flushWorkspaceChange, 300)
}

function handleSaveShortcut(event) {
  if (!(event.ctrlKey || event.metaKey) || event.altKey || String(event.key).toLowerCase() !== 's') return
  event.preventDefault()
  emit('save')
}

watch(() => props.modelValue, async (xml) => {
  if (!workspaceRef.value || xml === lastEmittedXml) {
    lastEmittedXml = ''
    return
  }
  await replaceBlocklyWorkspace(workspaceRef.value, xml)
  generatePreview()
  resizeWorkspace()
})

onMounted(async () => {
  await nextTick()
  if (!hostRef.value) return
  const workspace = createBlocklyWorkspace(hostRef.value, props.modelValue)
  workspaceRef.value = workspace
  // 保持现有主题切换入口可用，统一编辑器仍然只有一个活动 Blockly 工作区。
  state.blocklyEditor.value = workspace
  workspace.addChangeListener(scheduleWorkspaceChange)
  resizeObserver = new ResizeObserver(resizeWorkspace)
  resizeObserver.observe(hostRef.value)
  window.addEventListener('keydown', handleSaveShortcut)
  generatePreview()
  resizeWorkspace()
})

onBeforeUnmount(() => {
  if (changeTimer) window.clearTimeout(changeTimer)
  window.removeEventListener('keydown', handleSaveShortcut)
  resizeObserver?.disconnect()
  if (state.blocklyEditor.value === workspaceRef.value) state.blocklyEditor.value = null
  workspaceRef.value?.dispose()
  workspaceRef.value = null
})
</script>

<template>
  <div ref="hostRef" class="blockly-document-editor" />
</template>

<style scoped>
.blockly-document-editor {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-surface);
}
</style>
