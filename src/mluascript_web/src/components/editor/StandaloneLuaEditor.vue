<script setup>
import { computed } from 'vue'
import { NButton, NSpace, NText } from 'naive-ui'
import { actions, state } from '../../store'
import TextCodeEditor from './TextCodeEditor.vue'

const emit = defineEmits(['close'])
const displayPath = computed(() => state.savePath.value || state.filename.value || '未命名 Lua')
const dirty = computed(() => state.luaCode.value !== state.lastSessionLuaCode.value)

function setContent(content) {
  state.luaCode.value = content
}

async function saveLua() {
  try {
    await actions.saveStandaloneLuaFile()
  } catch (error) {
    actions.setStatus(error?.message || '保存 Lua 文件失败', 'error')
  }
}

async function runLua() {
  try {
    await actions.runLuaScript(null, state.luaCode.value)
  } catch (error) {
    actions.setStatus(error?.message || '执行 Lua 失败', 'error')
  }
}
</script>

<template>
  <section class="standalone-lua-editor">
    <header class="standalone-toolbar">
      <div class="standalone-title">
        <n-text strong>单文件 Lua</n-text>
        <n-text depth="3" class="standalone-path">{{ displayPath }}</n-text>
      </div>
      <n-space size="small">
        <n-button size="small" @click="emit('close')">项目列表</n-button>
        <n-button size="small" type="primary" @click="saveLua">保存</n-button>
        <n-button size="small" type="primary" secondary @click="runLua">直接执行</n-button>
      </n-space>
    </header>

    <main class="standalone-editor-host">
      <text-code-editor
        :path="displayPath"
        :model-value="state.luaCode.value"
        @update:model-value="setContent"
        @save="saveLua"
      />
    </main>

    <footer class="standalone-statusbar">
      <span>{{ dirty ? '尚未保存' : '已保存' }}</span>
      <span>兼容旧版单文件 Lua</span>
      <span class="status-spacer" />
      <span>{{ state.statusText.value }}</span>
    </footer>
  </section>
</template>

<style scoped>
.standalone-lua-editor {
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
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
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
