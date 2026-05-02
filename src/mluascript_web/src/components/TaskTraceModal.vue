<script setup>
import { computed } from 'vue'
import { NCard, NScrollbar, NEmpty, NTag, NSpace, NText, NSelect, NButton } from 'naive-ui'
import { state, actions } from '../store'

const props = defineProps({
  taskId: {
    type: String,
    default: '',
  },
  mode: {
    type: String,
    default: 'logs',
  },
})

const task = computed(() => state.taskDetailById.value[props.taskId] || state.tasks.value.find((item) => item.task_id === props.taskId) || null)
const selectedLevel = computed({
  get: () => state.taskTraceLevelFilter?.value || 'all',
  set: (value) => {
    if (state.taskTraceLevelFilter?.value !== undefined) state.taskTraceLevelFilter.value = value
  },
})

const levelOptions = [
  { label: '所有级别', value: 'all' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARN', value: 'WARN' },
  { label: 'ERROR', value: 'ERROR' },
]

const traceSource = computed(() => {
  if (props.mode === 'output') {
    return state.taskOutputById.value[props.taskId] || null
  }
  return state.taskLogsById.value[props.taskId] || null
})

const items = computed(() => {
  if (!traceSource.value) return []
  if (props.mode === 'output') {
    return Array.isArray(traceSource.value.items) ? traceSource.value.items.map(item => String(item)) : []
  }
  const rawItems = Array.isArray(traceSource.value.items) ? traceSource.value.items : []
  if (selectedLevel.value === 'all') return rawItems
  return rawItems.filter((item) => {
    const level = String(item?.level || 'INFO').toUpperCase()
    if (selectedLevel.value === 'WARN') {
      return level === 'WARN' || level === 'WARNING'
    }
    return level === selectedLevel.value
  })
})

function levelType(level) {
  const l = String(level || '').toUpperCase()
  if (l === 'ERROR' || l === 'FATAL') return 'error'
  if (l === 'WARN' || l === 'WARNING') return 'warning'
  if (l === 'SUCCESS') return 'success'
  return 'default'
}

function formatLog(item) {
  if (item && typeof item === 'object') {
    return {
      level: String(item.level || 'INFO').toUpperCase(),
      message: String(item.message || ''),
    }
  }
  return {
    level: 'INFO',
    message: String(item || ''),
  }
}

async function copyTraceLine(item, index) {
  const text = props.mode === 'output'
    ? `${index + 1}. ${String(item || '')}`
    : `[${formatLog(item).level}] ${formatLog(item).message}`
  await navigator.clipboard.writeText(text)
  actions.setStatus('已复制该条内容', 'success')
}

async function copyAllTrace() {
  const text = props.mode === 'output'
    ? items.value.map((item, index) => `${index + 1}. ${String(item || '')}`).join('\n')
    : items.value.map((item) => `[${formatLog(item).level}] ${formatLog(item).message}`).join('\n')
  await navigator.clipboard.writeText(text)
  actions.setStatus(`已复制 ${items.value.length} 条内容`, 'success')
}
</script>

<template>
  <div class="task-trace-modal">
    <n-card v-if="task" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
          <span>{{ mode === 'output' ? '任务输出' : '任务日志' }}</span>
          <n-space>
            <n-tag>{{ task.kind }}</n-tag>
            <n-tag>{{ task.status }}</n-tag>
          </n-space>
        </div>
      </template>

      <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
        <n-text depth="3">{{ task.title || task.name || task.task_id }}</n-text>
        <n-space>
          <n-select v-if="mode === 'logs'" v-model:value="selectedLevel" :options="levelOptions" size="small" style="width: 120px;" />
          <n-button size="small" @click="copyAllTrace">复制全部</n-button>
        </n-space>
      </div>

      <div class="trace-shell">
        <n-scrollbar>
          <div v-if="mode === 'output'" class="trace-list">
            <div v-for="(line, index) in items" :key="`${index}-${line}`" class="trace-item output-item">
              <span class="trace-index">{{ index + 1 }}</span>
              <pre class="trace-message">{{ line }}</pre>
              <div class="trace-actions">
                <n-button text size="tiny" @click="copyTraceLine(line, index)">复制</n-button>
              </div>
            </div>
            <n-empty v-if="!items.length" description="暂无输出" style="margin-top: 40px;" />
          </div>
          <div v-else class="trace-list">
            <div v-for="(item, index) in items" :key="`${index}-${formatLog(item).message}`" class="trace-item" :class="`level-${levelType(formatLog(item).level)}`">
              <div class="trace-meta">
                <span class="trace-index">{{ index + 1 }}</span>
                <span class="trace-level" :class="`text-${levelType(formatLog(item).level)}`">{{ formatLog(item).level }}</span>
              </div>
              <pre class="trace-message">{{ formatLog(item).message }}</pre>
              <div class="trace-actions">
                <n-button text size="tiny" @click="copyTraceLine(item, index)">复制</n-button>
              </div>
            </div>
            <n-empty v-if="!items.length" description="暂无日志" style="margin-top: 40px;" />
          </div>
        </n-scrollbar>
      </div>
    </n-card>
    <n-card v-else :bordered="false" size="small">任务不存在或已被移除</n-card>
  </div>
</template>

<style scoped>
.task-trace-modal {
  height: 100%;
}

.trace-shell {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  background: var(--n-color-embedded);
  overflow: hidden;
}

.trace-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-list :deep(.n-empty__description), .trace-list :deep(.n-empty__icon) {
  color: #858585;
}

.trace-item {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  gap: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  border: none;
  background: transparent;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.output-item {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.trace-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.trace-item.level-error {
  background: rgba(244, 135, 113, 0.1);
}

.trace-item.level-warning {
  background: rgba(204, 167, 0, 0.1);
}

.trace-meta {
  display: contents;
}

.trace-index {
  color: #858585;
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.trace-level {
  display: inline-flex;
  min-width: 48px;
  font-size: 13px;
  font-weight: bold;
  text-transform: uppercase;
}

.text-default, .text-info {
  color: #3b8eea;
}

.text-error {
  color: #f48771;
}

.text-warning {
  color: #cca700;
}

.text-success {
  color: #89d185;
}

.trace-message {
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

.trace-item.level-error .trace-message {
  color: #f48771;
}

.trace-item.level-warning .trace-message {
  color: #cca700;
}

.trace-actions {
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  align-items: flex-start;
}

.trace-item:hover .trace-actions {
  opacity: 1;
}

.trace-actions :deep(.n-button) {
  color: #858585;
}

.trace-actions :deep(.n-button:hover) {
  color: #cccccc;
}
</style>
