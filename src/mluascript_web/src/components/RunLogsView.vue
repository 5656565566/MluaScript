<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { NCard, NSelect, NButton, NCheckbox, NSpace, NText, NScrollbar, NEmpty } from 'naive-ui'
import { state, actions } from '../store'

const selectedLevel = computed({
  get: () => state.runLogsSelectedLevel.value,
  set: value => { state.runLogsSelectedLevel.value = value },
})
const autoScroll = computed({
  get: () => state.runLogsAutoScroll.value,
  set: value => { state.runLogsAutoScroll.value = value },
})
const scrollbarRef = ref(null)

const levelOptions = [
  { label: '所有级别', value: 'all' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARN', value: 'WARN' },
  { label: 'ERROR', value: 'ERROR' }
]

const runtimeLogs = computed(() => state.logs.value)

const filteredLogs = computed(() => {
  let logs = runtimeLogs.value
  if (selectedLevel.value !== 'all') {
    logs = logs.filter(log => {
      const level = (log.level || 'INFO').toUpperCase()
      if (selectedLevel.value === 'WARN') {
        return level === 'WARN' || level === 'WARNING'
      }
      return level === selectedLevel.value
    })
  }
  return logs
})

const logStats = computed(() => {
  const stats = { total: runtimeLogs.value.length, info: 0, error: 0, warn: 0 }
  runtimeLogs.value.forEach(log => {
    const level = (log.level || 'INFO').toUpperCase()
    if (level === 'ERROR') stats.error++
    else if (level === 'WARN' || level === 'WARNING') stats.warn++
    else stats.info++
  })
  return stats
})

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function clearLogs() {
  state.logs.value = []
}

function scrollToBottom() {
  if (scrollbarRef.value) {
    scrollbarRef.value.scrollTo({ position: 'bottom' })
  }
}

async function copyLogLine(log) {
  const line = `${formatTime(log.ts)} [${String(log.level || 'INFO').toUpperCase()}] ${log.message || ''}`
  await navigator.clipboard.writeText(line)
  actions.setStatus('已复制该条日志', 'success')
}

async function copyAllLogs() {
  const text = filteredLogs.value
    .map(log => `${formatTime(log.ts)} [${String(log.level || 'INFO').toUpperCase()}] ${log.message || ''}`)
    .join('\n')
  await navigator.clipboard.writeText(text)
  actions.setStatus(`已复制 ${filteredLogs.value.length} 条日志`, 'success')
}

watch(filteredLogs, async () => {
  if (autoScroll.value) {
    await nextTick()
    scrollToBottom()
  }
})

function getLevelType(level) {
  const l = (level || '').toUpperCase()
  if (l === 'ERROR') return 'error'
  if (l === 'WARN' || l === 'WARNING') return 'warning'
  return 'info'
}
</script>

<template>
  <n-card class="run-logs-view" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <n-space align="center">
          <span>运行日志</span>
          <n-select v-model:value="selectedLevel" :options="levelOptions" size="small" style="width: 120px;" />
        </n-space>
        
        <n-space align="center">
          <n-text depth="3" style="font-size: 12px;">
            <span style="margin-right: 8px;">{{ logStats.total }} 条</span>
            <span v-if="logStats.error" style="color: var(--n-error-color); margin-right: 8px;">{{ logStats.error }} 错误</span>
            <span v-if="logStats.warn" style="color: var(--n-warning-color); margin-right: 8px;">{{ logStats.warn }} 警告</span>
          </n-text>
          
          <n-checkbox v-model:checked="autoScroll">自动滚动</n-checkbox>
          <n-button size="small" @click="copyAllLogs">复制全部</n-button>
          <n-button size="small" @click="actions.refreshLogs('runtime')">刷新</n-button>
          <n-button size="small" @click="clearLogs">清空</n-button>
        </n-space>
      </div>
    </template>
    
    <div class="run-log-shell">
      <n-scrollbar ref="scrollbarRef" x-scrollable>
        <div class="run-log-list">
          <div
            v-for="(log, index) in filteredLogs"
            :key="`${index}-${log.ts || index}`"
            class="run-log-item"
            :class="`level-${getLevelType(log.level)}`"
          >
            <div class="run-log-meta">
              <span class="run-log-time">{{ formatTime(log.ts) }}</span>
              <span class="run-log-level" :class="`text-${getLevelType(log.level)}`">{{ log.level || 'INFO' }}</span>
            </div>
            <pre class="run-log-message">{{ log.message }}</pre>
            <div class="run-log-actions">
              <n-button text size="tiny" @click="copyLogLine(log)">复制</n-button>
            </div>
          </div>
          <n-empty v-if="!filteredLogs.length" description="暂无日志记录" style="margin-top: 40px;" />
        </div>
      </n-scrollbar>
    </div>
  </n-card>
</template>

<style scoped>
.run-logs-view :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  padding: 0 16px 16px;
  flex: 1;
  min-height: 0;
}

.run-log-shell {
  flex: 1;
  min-height: 0;
  background: var(--n-color-embedded);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
}

.run-log-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.run-log-list :deep(.n-empty__description), .run-log-list :deep(.n-empty__icon) {
  color: var(--color-text-muted);
}

.run-log-item {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  gap: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  border: none;
  background: transparent;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.run-log-item:hover {
  background: var(--color-border-light);
}

.run-log-item.level-error {
  background: color-mix(in srgb, var(--color-danger) 10%, transparent);
}

.run-log-item.level-warning {
  background: color-mix(in srgb, var(--color-warning) 10%, transparent);
}

.run-log-meta {
  display: contents;
}

.run-log-time {
  color: var(--color-text-muted);
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.run-log-level {
  display: inline-flex;
  min-width: 48px;
  font-size: 13px;
  font-weight: bold;
  text-transform: uppercase;
}

.text-info {
  color: var(--color-info);
}

.text-error {
  color: var(--color-danger);
}

.text-warning {
  color: var(--color-warning);
}

.run-log-message {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: var(--n-text-color);
  font-size: 13px;
  line-height: 1.5;
  user-select: text;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.run-log-item.level-error .run-log-message {
  color: var(--color-danger);
}

.run-log-item.level-warning .run-log-message {
  color: var(--color-warning);
}

.run-log-actions {
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  align-items: flex-start;
}

.run-log-item:hover .run-log-actions {
  opacity: 1;
}

.run-log-actions :deep(.n-button) {
  color: var(--n-text-color-3);
}

.run-log-actions :deep(.n-button:hover) {
  color: var(--n-text-color-1);
}
</style>
