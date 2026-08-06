<script setup>
import { computed } from 'vue'
import { NButton, NEmpty, NSpace, NText } from 'naive-ui'
import { actions, state } from '../../store'
import BlocklyEditorPane from './BlocklyEditorPane.vue'
import LuaPreviewDrawer from './LuaPreviewDrawer.vue'

const hasBlocklyDocument = computed(() => Boolean(
  state.blocklyXml.value
  || state.blocklySavePath.value
  || state.blocklyFilename.value,
))
const emit = defineEmits(['close'])

function setBlocklyContent(xml) {
  state.blocklyXml.value = xml
}

function handleBlocklyGenerated(code, diagnostics, stale) {
  state.luaCode.value = code || ''
  state.blocklyGenerationError.value = stale
    ? diagnostics.find(item => item?.severity === 'error')?.message || 'Lua 生成失败'
    : ''
}

async function saveBlockly() {
  try {
    await actions.saveBlocklyWorkspace()
  } catch (error) {
    actions.setStatus(error?.message || '保存 Blockly 文件失败', 'error')
  }
}

async function runBlocklyLua() {
  try {
    await actions.runCurrentBlocklyLua()
  } catch (error) {
    actions.setStatus(error?.message || '执行 Blockly Lua 失败', 'error')
  }
}
</script>

<template>
  <section class="standalone-blockly-editor">
    <header class="standalone-toolbar">
      <div class="standalone-title">
        <n-text strong>单文件 Blockly</n-text>
        <n-text depth="3" class="standalone-path">
          {{ state.blocklySavePath.value || state.blocklyFilename.value || '未命名 Blockly' }}
        </n-text>
      </div>
      <n-space size="small">
        <n-button size="small" @click="emit('close')">项目列表</n-button>
        <n-button size="small" @click="actions.openBlocklyWorkspaceManager()">文件管理</n-button>
        <n-button size="small" @click="state.projectLuaPreviewVisible.value = true">Lua 预览</n-button>
        <n-button size="small" type="primary" @click="saveBlockly">保存</n-button>
        <n-button size="small" type="primary" secondary @click="runBlocklyLua">直接执行</n-button>
      </n-space>
    </header>

    <main class="standalone-editor-host">
      <blockly-editor-pane
        v-if="hasBlocklyDocument"
        :model-value="state.blocklyXml.value"
        @update:model-value="setBlocklyContent"
        @generated="handleBlocklyGenerated"
        @save="saveBlockly"
      />
      <n-empty v-else description="尚未打开 Blockly 文件">
        <template #extra>
          <n-button type="primary" @click="actions.openBlocklyWorkspaceManager()">打开文件管理</n-button>
        </template>
      </n-empty>
    </main>

    <footer class="standalone-statusbar">
      <span>兼容旧版单文件 Blockly 工作区</span>
      <span class="status-spacer" />
      <span>{{ state.statusText.value }}</span>
    </footer>
  </section>

  <lua-preview-drawer
    :show="state.projectLuaPreviewVisible.value"
    :code="state.luaCode.value"
    :diagnostics="state.blocklyGenerationError.value ? [{ severity: 'error', message: state.blocklyGenerationError.value }] : []"
    :stale="Boolean(state.blocklyGenerationError.value)"
    @update:show="value => state.projectLuaPreviewVisible.value = value"
  />
</template>

<style scoped>
.standalone-blockly-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 10px;
  box-sizing: border-box;
  background: var(--color-background);
}

.standalone-toolbar,
.standalone-statusbar {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.standalone-toolbar {
  justify-content: space-between;
  min-height: 42px;
  padding: 0 10px;
  border-radius: 6px 6px 0 0;
}

.standalone-title {
  min-width: 0;
}

.standalone-path {
  margin-left: 10px;
  font-size: 12px;
}

.standalone-editor-host {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
}

.standalone-editor-host > :deep(.n-empty) {
  margin: auto;
}

.standalone-statusbar {
  flex: 0 0 26px;
  padding: 0 10px;
  color: var(--color-text-secondary);
  background: var(--color-surface-2);
  font-size: 11px;
}

.status-spacer {
  flex: 1;
}

@media (max-width: 680px) {
  .standalone-toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding: 8px;
  }
}
</style>
