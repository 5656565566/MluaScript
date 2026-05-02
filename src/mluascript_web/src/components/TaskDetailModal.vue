<script setup>
import { computed } from 'vue'
import { NCard, NDescriptions, NDescriptionsItem, NTag, NButton, NSpace, NText } from 'naive-ui'
import { state, actions } from '../store'

const props = defineProps({
  taskId: {
    type: String,
    default: '',
  },
})

const task = computed(() => state.taskDetailById.value[props.taskId] || null)

const statusTypeMap = {
  running: 'primary',
  success: 'success',
  failed: 'error',
  stopped: 'warning',
  pending: 'default',
}

function formatValue(value) {
  if (value === null || typeof value === 'undefined' || value === '') return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <div class="task-detail-modal">
    <n-card v-if="task" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;">
      <div class="task-detail-header">
        <div>
          <div class="task-title">{{ task.title || task.task_id }}</div>
          <n-text depth="3">{{ task.task_id }}</n-text>
        </div>
        <n-space>
          <n-tag :type="statusTypeMap[task.status] || 'default'">{{ task.status }}</n-tag>
          <n-tag>{{ task.kind }}</n-tag>
        </n-space>
      </div>

      <n-descriptions label-placement="top" :column="2" bordered size="small">
        <n-descriptions-item label="任务 ID">
          <pre class="task-pre">{{ task.task_id }}</pre>
        </n-descriptions-item>
        <n-descriptions-item label="目标">
          <pre class="task-pre">{{ task.target || '-' }}</pre>
        </n-descriptions-item>
        <n-descriptions-item label="标题">
          <pre class="task-pre">{{ task.title || '-' }}</pre>
        </n-descriptions-item>
        <n-descriptions-item label="状态">
          <pre class="task-pre">{{ task.status || '-' }}</pre>
        </n-descriptions-item>
        <n-descriptions-item label="结果" :span="2">
          <pre class="task-pre">{{ formatValue(task.result) }}</pre>
        </n-descriptions-item>
        <n-descriptions-item label="错误" :span="2">
          <pre class="task-pre">{{ formatValue(task.error) }}</pre>
        </n-descriptions-item>
      </n-descriptions>

      <div class="task-detail-actions">
        <n-space>
          <n-button :disabled="!task.capabilities?.has_logs" @click="actions.openTaskLogsModal(task.task_id)">查看日志</n-button>
          <n-button :disabled="!task.capabilities?.has_output" @click="actions.openTaskOutputModal(task.task_id)">查看输出</n-button>
          <n-button :disabled="!task.capabilities?.can_stop" @click="actions.handleAction(() => actions.stopTask(task.task_id))">停止</n-button>
          <n-button type="error" :disabled="!task.capabilities?.can_remove" @click="actions.handleAction(() => actions.removeTask(task.task_id))">删除</n-button>
        </n-space>
      </div>
    </n-card>
    <n-card v-else :bordered="false" size="small">任务不存在或已被移除</n-card>
  </div>
</template>

<style scoped>
.task-detail-modal {
  height: 100%;
}

.task-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.task-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.6;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.task-detail-actions {
  margin-top: 16px;
}
</style>
