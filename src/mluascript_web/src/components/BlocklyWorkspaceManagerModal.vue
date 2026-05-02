<script setup>
import { computed, onUnmounted } from 'vue'
import { NCard, NInput, NList, NListItem, NThing, NButton, NEmpty, NSpace, NText, NIcon } from 'naive-ui'
import { state, getters, actions } from '../store'

const blocklyFiles = computed(() => getters.filteredBlocklyFiles.value)
const currentBlocklyPath = computed(() => state.blocklySavePath.value || state.blocklyFilename.value || '未命名')
const currentLuaPath = computed(() => state.savePath.value || state.filename.value || '未命名')

onUnmounted(() => {
  state.blocklyWorkspaceManagerModalId.value = null
})
</script>

<template>
  <n-card class="blockly-workspace-manager" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap;">
        <n-space align="center">
          <span>文件管理</span>
          <n-text depth="3" style="font-size: 12px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="currentBlocklyPath">
            {{ currentBlocklyPath }}
          </n-text>
        </n-space>
        <n-space>
          <n-input v-model:value="state.blocklyManagerQuery.value" placeholder="搜索 Blockly 文件" clearable style="width: 220px;">
            <template #prefix><n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M456.69 421.39L362.6 327.3a173.81 173.81 0 0 0 34.84-104.58C397.44 126.38 319.06 48 222.72 48S48 126.38 48 222.72s78.38 174.72 174.72 174.72A173.81 173.81 0 0 0 327.3 362.6l94.09 94.09a25 25 0 0 0 35.3-35.3zM97.92 222.72a124.8 124.8 0 1 1 124.8 124.8a124.95 124.95 0 0 1-124.8-124.8z" fill="currentColor"></path></svg></n-icon></template>
          </n-input>
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.saveBlocklyWorkspace)">保存当前编辑内容</n-button>
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.loadState)">刷新</n-button>
        </n-space>
      </div>
    </template>

    <div class="blockly-workspace-layout">
      <n-card title="当前编辑文件" size="small" :bordered="true" class="workspace-panel">
        <div class="workspace-current-grid">
          <div class="workspace-field">
            <n-text depth="3" style="font-size: 12px;">Blockly 文件名</n-text>
            <n-input v-model:value="state.blocklyFilename.value" placeholder="blockly 名称.xml" />
          </div>
          <div class="workspace-field">
            <n-text depth="3" style="font-size: 12px;">Lua 文件名</n-text>
            <n-input v-model:value="state.filename.value" placeholder="lua 名称.lua" />
          </div>
        </div>

        <div class="workspace-actions">
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.saveLuaScript)">保存 Lua</n-button>
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.saveBlocklyWorkspace)">保存 Blockly</n-button>
          <n-button type="primary" size="small" :loading="state.loading.value" @click="actions.handleAction(() => actions.runLuaScript(null, state.luaCode.value))">直接执行 Lua</n-button>
        </div>

        <div class="workspace-meta-box">
          <n-text depth="3">当前 Blockly：{{ currentBlocklyPath }}</n-text>
          <n-text depth="3">当前 Lua：{{ currentLuaPath }}</n-text>
          <n-text depth="3">Lua 预览来源：编辑器会话</n-text>
        </div>
      </n-card>

      <n-card title="已保存的 Blockly 文件" size="small" :bordered="true" class="workspace-panel">
        <template #header-extra>
          <n-text depth="3">{{ blocklyFiles.length }} 个</n-text>
        </template>
        <n-list hoverable clickable class="workspace-file-list">
          <n-empty v-if="!blocklyFiles.length" description="暂无匹配 Blockly 文件" style="margin-top: 24px;" />
          <n-list-item v-for="file in blocklyFiles" :key="file.path">
            <n-thing>
              <template #header>{{ file.name }}</template>
              <template #description>
                <n-text depth="3" style="word-break: break-all;">{{ file.path }}</n-text>
              </template>
            </n-thing>
            <template #suffix>
              <n-space vertical align="end">
                <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(() => actions.loadBlocklyWorkspace(file.name))">加载</n-button>
                <n-button size="small" @click="actions.closeBlocklyWorkspaceManager()">关闭</n-button>
              </n-space>
            </template>
          </n-list-item>
        </n-list>
      </n-card>
    </div>
  </n-card>
</template>

<style scoped>
.blockly-workspace-manager :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 0 16px 16px;
}

.blockly-workspace-layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(420px, 1.1fr);
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.workspace-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.workspace-panel :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 0;
}

.workspace-current-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.workspace-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.workspace-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.workspace-meta-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color-embedded);
}

.workspace-file-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: transparent;
}

@media (max-width: 1024px) {
  .blockly-workspace-layout {
    grid-template-columns: 1fr;
  }
}
</style>
