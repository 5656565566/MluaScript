<script setup>
import { computed } from 'vue'
import { NCard, NAlert, NButton, NInput, NSpace, NTag, NText, NIcon, NEmpty, NSelect } from 'naive-ui'
import { state, actions } from '../store'

const searchQuery = computed({
  get: () => state.deviceManagerQuery.value,
  set: value => { state.deviceManagerQuery.value = value },
})

const previewIntervalOptions = [
  { label: '0.5 秒', value: 500 },
  { label: '1 秒', value: 1000 },
  { label: '2 秒', value: 2000 },
  { label: '5 秒', value: 5000 },
]

const filteredSessions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) {
    return state.sessions.value
  }
  return state.sessions.value.filter(session =>
    (session.label || '').toLowerCase().includes(query)
  )
})

function selectSession(session) {
  if (state.selectedSession.value === session.label) {
    state.selectedSession.value = ''
  } else {
    state.selectedSession.value = session.label
  }
}
</script>

<template>
  <n-card class="device-manager-view" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span>设备管理</span>
        <n-space wrap>
          <n-button size="small" :disabled="!state.selectedSession.value" :loading="state.loading.value" @click="actions.handleAction(actions.doScreencap)">截图测试</n-button>
          <n-button size="small" :disabled="!state.selectedSession.value" :loading="state.loading.value" @click="actions.handleAction(actions.openDevicePreviewWindow)">打开预览窗</n-button>
          <n-select
            :value="state.devicePreviewIntervalMs.value"
            :options="previewIntervalOptions"
            size="small"
            style="width: 110px;"
            @update:value="actions.setDevicePreviewInterval"
          />
          <n-button size="small" type="error" secondary :disabled="!state.selectedSession.value" :loading="state.loading.value" @click="actions.handleAction(() => actions.disconnectSession())">断开当前设备</n-button>
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.reloadSessions)">刷新</n-button>
        </n-space>
      </div>
    </template>

    <div class="device-manager-content">
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div style="margin-bottom: 12px; display: flex; gap: 12px;">
          <n-input v-model:value="searchQuery" placeholder="搜索设备名称..." clearable>
            <template #prefix>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M456.69 421.39L362.6 327.3a173.81 173.81 0 0 0 34.84-104.58C397.44 126.38 319.06 48 222.72 48S48 126.38 48 222.72s78.38 174.72 174.72 174.72A173.81 173.81 0 0 0 327.3 362.6l94.09 94.09a25 25 0 0 0 35.3-35.3zM97.92 222.72a124.8 124.8 0 1 1 124.8 124.8a124.95 124.95 0 0 1-124.8-124.8z" fill="currentColor"></path></svg></n-icon>
            </template>
          </n-input>
        </div>

        <div class="device-list-scroll">
          <div
            v-for="session in filteredSessions"
            :key="session.label"
            class="device-item"
            :class="{ active: state.selectedSession.value === session.label }"
            @click="selectSession(session)"
          >
            <div class="device-item-header">
              <span class="device-item-title">{{ session.label }}</span>
              <n-tag size="small" type="success" round :bordered="false" v-if="session.connected">已连接</n-tag>
              <n-tag size="small" type="warning" round :bordered="false" v-else>未连接</n-tag>
            </div>
            <div class="device-item-meta">
              <n-text depth="3" style="font-size: 13px;">{{ session.canScreencap ? '支持截图' : '不支持截图' }}</n-text>
            </div>
          </div>

          <n-empty v-if="!filteredSessions.length" description="未发现可用设备" style="margin-top: 40px;" />
        </div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.device-manager-view :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  padding: 0 16px 16px;
  flex: 1;
  min-height: 0;
}

.device-manager-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.device-list-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 8px;
}

.device-item {
  border-radius: 6px;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid var(--n-border-color);
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
  background-color: transparent;
}

.device-item:hover {
  border-color: var(--n-primary-color);
}

.device-item.active {
  border-color: var(--n-primary-color);
  background-color: color-mix(in srgb, var(--n-primary-color) 10%, transparent);
}

.device-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.device-item-title {
  font-weight: 500;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
