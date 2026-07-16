<script setup>
import { onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as Blockly from 'blockly'
import { state, getters, actions } from '../store'
import { createBlocklyWorkspace } from '../blockly'
import { NCard, NSpace, NButton, NText } from 'naive-ui'

let syncTimer = null

function resizeBlockly() {
  window.requestAnimationFrame(() => {
    if (!state.blocklyEditor.value || !state.blocklyEditorRef.value || state.activeView.value !== 'blockly') return
    const host = state.blocklyEditorRef.value
    if (!host.offsetWidth || !host.offsetHeight) return
    state.blocklyEditor.value.resize()
    Blockly.svgResize(state.blocklyEditor.value)
  })
}

function setEditorLayout(layout) {
  state.editorLayout.value = layout
  resizeBlockly()
}

watch(() => state.editorLayout.value, async () => {
  await nextTick()
  resizeBlockly()
})

watch(() => state.sidebarCollapsed.value, async () => {
  setTimeout(() => {
    resizeBlockly()
  }, 300)
})

watch(() => state.showScreenshot.value, async (visible) => {
  await nextTick()
  if (visible && state.activeView.value === 'device') actions.placeScreenshotDock()
  resizeBlockly()
})

onMounted(async () => {
  await nextTick()
  if (state.blocklyEditorRef.value) {
    state.blocklyEditor.value = createBlocklyWorkspace(state.blocklyEditorRef.value, state.blocklyXml.value)
    state.blocklyEditor.value.addChangeListener((event) => {
      if (event?.isUiEvent) return
      if (state.suppressBlocklyAutosave.value) return
      if (event.type === Blockly.Events.FINISHED_LOADING) return

      if (syncTimer) window.clearTimeout(syncTimer)
      syncTimer = window.setTimeout(() => {
        actions.rebuildLuaCode()
        const hasRealChange = state.blocklyXml.value !== state.lastSavedBlocklyXml.value

        actions.syncWorkspace().catch((error) => {
          console.error(error)
        })
        if (state.autoSaveBlockly.value && hasRealChange) {
          actions.saveBlocklyWorkspace(false).catch((error) => {
            console.error(error)
          })
        }
      }, 300)
    })
    actions.rebuildLuaCode()
    await actions.syncWorkspace()
  }
  resizeBlockly()
  window.addEventListener('resize', resizeBlockly)
})

onBeforeUnmount(() => {
  if (syncTimer) {
    window.clearTimeout(syncTimer)
    actions.rebuildLuaCode()
    const hasRealChange = state.blocklyXml.value !== state.lastSavedBlocklyXml.value
    actions.syncWorkspace().catch((error) => console.error(error))
    if (state.autoSaveBlockly.value && hasRealChange) {
      actions.saveBlocklyWorkspace(false).catch((error) => console.error(error))
    }
  }
  window.removeEventListener('resize', resizeBlockly)
  if (state.blocklyEditor.value) state.blocklyEditor.value.dispose()
  state.blocklyEditor.value = null
  state.blocklyEditorRef.value = null
})
</script>

<template>
<section class="blockly-editor-view" style="display: flex; flex-direction: column; gap: 8px; padding: 10px; height: 100%; box-sizing: border-box;">
  <div style="display: flex; justify-content: space-between; align-items: center; background: var(--n-color); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--n-border-color);">
    <n-space>
      <n-button-group size="small">
        <n-button :type="state.editorLayout.value === 'split' ? 'primary' : 'default'" @click="setEditorLayout('split')">左右</n-button>
        <n-button :type="state.editorLayout.value === 'blockly-only' ? 'primary' : 'default'" @click="setEditorLayout('blockly-only')">仅 Blockly</n-button>
        <n-button :type="state.editorLayout.value === 'lua-only' ? 'primary' : 'default'" @click="setEditorLayout('lua-only')">仅 Lua</n-button>
      </n-button-group>

      <n-button size="small" type="primary" @click="actions.openBlocklyWorkspaceManager()">文件管理</n-button>
    </n-space>

    <n-space align="center">
      <n-text depth="3" style="font-size: 12px;">{{ state.statusText.value }}</n-text>
      <n-text depth="3" style="font-size: 12px;">当前 Blockly：{{ state.blocklyFilename.value || '未命名' }}</n-text>
    </n-space>
  </div>

  <div :class="getters.editorPaneClass.value" style="flex: 1; min-height: 0;">
    <n-card v-show="state.editorLayout.value !== 'lua-only'" class="blockly-panel" :bordered="true" style="height: 100%; min-width: 0; min-height: 0; display: flex; flex-direction: column;" content-style="padding: 0; flex: 1; min-height: 0; display: flex; flex-direction: column;">
      <div :ref="(el) => state.blocklyEditorRef.value = el" class="blockly-host" style="flex: 1; min-height: 0; border-radius: 4px; overflow: hidden;"></div>
    </n-card>
    <n-card v-show="state.editorLayout.value !== 'blockly-only'" class="lua-panel" :bordered="true" style="height: 100%; min-width: 0; min-height: 0; display: flex; flex-direction: column;" content-style="padding: 0; display: flex; flex-direction: column; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--n-border-color); background: var(--n-color-embedded);">
        <n-text strong>Lua 预览</n-text>
        <n-text depth="3" style="font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="state.savePath.value || '尚未保存'">{{ state.savePath.value || '尚未保存' }}</n-text>
      </div>
      <div style="flex: 1; min-height: 0; overflow: auto; padding: 12px; font-family: monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; background: var(--n-color);">
        {{ state.luaCode.value }}
      </div>
    </n-card>
  </div>
</section>
</template>

<style scoped>
.editor-pane {
  display: grid;
  gap: 8px;
  height: 100%;
  width: 100%;
}

.editor-pane.layout-split {
  grid-template-columns: minmax(0, 1.7fr) minmax(320px, 0.9fr);
}

@media (max-width: 768px) {
  .editor-pane.layout-split {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 1fr;
  }
}

.editor-pane.layout-blockly-only {
  grid-template-columns: 1fr;
}

.editor-pane.layout-lua-only {
  grid-template-columns: 1fr;
}

.blockly-host .blocklyToolboxDiv {
  background: var(--n-color-embedded) !important;
  border-right: none !important;
}

.blockly-host .blocklyFlyout .blocklyWorkspace,
.blockly-host .blocklyFlyout .blocklyBlockCanvas {
  margin-bottom: 24px !important;
  padding-bottom: 24px !important;
}

.blockly-host .blocklyFlyout .blocklyFlyoutBackground {
  height: calc(100% - 24px) !important;
}

.blockly-host .blocklyTreeRow {
  fill: transparent !important;
}

.blockly-host .blocklyTreeRow:not(.blocklyTreeSelected):hover {
  background: var(--n-border-color) !important;
}

.blockly-host .blocklyTreeRow.blocklyTreeSelected {
  background: var(--n-primary-color) !important;
}

.blockly-host .blocklyTreeLabel {
  color: var(--n-text-color) !important;
  fill: var(--n-text-color) !important;
}
</style>
