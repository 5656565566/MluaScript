<script setup>
import { computed, h, watch, onBeforeUnmount } from 'vue'
import { state, getters, actions } from '../store'
import { NTabs, NTabPane, NCard, NInput, NButton, NSpace, NTag, NText, NIcon, NDataTable, NLayout, NLayoutSider, NLayoutContent, NEmpty, NDescriptions, NDescriptionsItem, NLog, NScrollbar } from 'naive-ui'

const activeTab = computed({
  get: () => state.taskManagerActiveTab.value,
  set: value => { state.taskManagerActiveTab.value = value },
})
const resourceQuery = computed({
  get: () => state.taskManagerResourceQuery.value,
  set: value => { state.taskManagerResourceQuery.value = value },
})

const statusTypeMap = {
  running: 'primary',
  success: 'success',
  failed: 'error',
  stopped: 'warning',
  pending: 'default',
}

const resourceData = computed(() => {
  const pipelines = getters.pipelineTasks.value.map(t => ({ ...t, _kind: 'pipeline' }))
  const luas = state.availableScripts.value.map(t => ({ ...t, _kind: 'lua' }))
  let list = [...pipelines, ...luas]
  const q = resourceQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(item => {
      const name = String(item.name || item.path || '').toLowerCase()
      const desc = String(item.description || '').toLowerCase()
      return name.includes(q) || desc.includes(q)
    })
  }
  return list
})

const resourceColumns = [
  { 
    title: '类型', 
    key: '_kind', 
    width: 100,
    render(row) {
      return h(NTag, { type: row._kind === 'pipeline' ? 'info' : 'success', size: 'small', bordered: false, round: true }, { default: () => row._kind === 'pipeline' ? 'Pipeline' : 'Lua' })
    }
  },
  { 
    title: '名称 / 路径', 
    key: 'name',
    render(row) {
      if (row._kind === 'lua') {
        return h('div', { style: 'display: flex; flex-direction: column; gap: 4px;' }, [
          h('span', { style: 'font-weight: 500;' }, row.name),
          h(NText, { depth: 3, style: 'font-size: 12px; word-break: break-all;' }, { default: () => row.path })
        ])
      }
      return h('div', { style: 'font-weight: 500;' }, row.name)
    }
  },
  { 
    title: '描述', 
    key: 'description',
    render(row) {
      return row.description || '-'
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'right',
    render(row) {
      return h(NButton, {
        size: 'small',
        type: 'primary',
        secondary: true,
        onClick: () => {
          actions.handleAction(async () => {
            if (row._kind === 'pipeline') {
              await actions.runPipelineTask(row.name)
              activeTab.value = 'task-status'
              return
            }
            try {
              const payload = await actions.loadTemplate(row.path)
              if (payload.hasTemplate) {
                state.activeView.value = 'template-runner'
                return
              }
              throw new Error('未定义模板元数据')
            } catch (error) {
              const message = String(error?.message || error || '')
              if (!message.includes('未定义模板元数据')) {
                throw error
              }
              await actions.runLuaScript(row.path, '')
              activeTab.value = 'task-status'
            }
          })
        }
      }, { default: () => '运行' })
    }
  }
]

const orderedTasks = computed(() => [...getters.filteredTaskManagerTasks.value].reverse())
const selectedTask = computed(() => state.selectedTask.value)
const taskDetail = computed(() => state.taskDetailById.value[state.selectedTaskId.value])

const taskLogs = computed(() => state.taskLogsById.value[state.selectedTaskId.value]?.items || [])
const taskOutput = computed(() => state.taskOutputById.value[state.selectedTaskId.value]?.items || [])

const logText = computed(() => {
  return taskLogs.value.map(item => {
    const level = String(item.level || 'INFO').toUpperCase()
    return `[${level}] ${item.message}`
  }).join('\n')
})

const outputText = computed(() => {
  return taskOutput.value.map(item => String(item)).join('\n')
})

function buildTaskDisplayTitle(task) {
  return task?.title || task?.metadata?.entry || task?.metadata?.script_path || task?.name || task?.task_id || '未命名任务'
}

function selectTask(task) {
  state.selectedTaskId.value = task.task_id
}

function getLevelType(level) {
  const l = String(level || '').toUpperCase()
  if (l === 'ERROR') return 'error'
  if (l === 'WARN' || l === 'WARNING') return 'warning'
  return 'info'
}

watch(() => state.selectedTaskId.value, (newId) => {
  if (newId) {
    actions.fetchTaskDetail(newId)
    actions.startSelectedTaskStreams(newId)
    return
  }
  actions.stopSelectedTaskStreams()
}, { immediate: true })

watch(orderedTasks, (tasks) => {
  if (tasks.length > 0 && !state.selectedTaskId.value) {
    state.selectedTaskId.value = tasks[0].task_id
  }
}, { immediate: true })

onBeforeUnmount(() => {
  actions.stopSelectedTaskStreams()
})

</script>

<template>
  <n-card class="task-manager-view" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;" content-style="display: flex; flex-direction: column; padding: 0 16px 16px; flex: 1; min-height: 0;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span>任务管理</span>
        <n-space>
          <n-button size="small" type="error" secondary @click="actions.stopTasks()">停止全部运行中任务</n-button>
          <n-button size="small" :loading="state.loading.value" @click="actions.handleAction(actions.loadState)">刷新</n-button>
        </n-space>
      </div>
    </template>

    <div class="task-tab-panel">
      <n-tabs type="line" animated class="task-manager-tabs" v-model:value="activeTab">
        
        <n-tab-pane name="resource-list" tab="任务列表">
          <div style="display: flex; flex-direction: column; height: 100%; gap: 12px;">
            <n-input v-model:value="resourceQuery" placeholder="搜索脚本名称或描述..." clearable>
              <template #prefix>
                <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M456.69 421.39L362.6 327.3a173.81 173.81 0 0 0 34.84-104.58C397.44 126.38 319.06 48 222.72 48S48 126.38 48 222.72s78.38 174.72 174.72 174.72A173.81 173.81 0 0 0 327.3 362.6l94.09 94.09a25 25 0 0 0 35.3-35.3zM97.92 222.72a124.8 124.8 0 1 1 124.8 124.8a124.95 124.95 0 0 1-124.8-124.8z" fill="currentColor"></path></svg></n-icon>
              </template>
            </n-input>
            <n-data-table
              :columns="resourceColumns"
              :data="resourceData"
              :bordered="true"
              flex-height
              style="flex: 1; min-height: 0;"
            />
          </div>
        </n-tab-pane>

        <n-tab-pane name="task-status" tab="任务状态">
          <n-layout has-sider style="height: 100%; background: transparent;">
            <n-layout-sider width="320" bordered style="background: transparent;">
              <div style="display: flex; flex-direction: column; height: 100%;">
                <div style="padding: 0 12px 12px 0;">
                  <n-input v-model:value="state.taskManagerQuery.value" placeholder="搜索已创建任务..." clearable size="small">
                    <template #prefix>
                      <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M456.69 421.39L362.6 327.3a173.81 173.81 0 0 0 34.84-104.58C397.44 126.38 319.06 48 222.72 48S48 126.38 48 222.72s78.38 174.72 174.72 174.72A173.81 173.81 0 0 0 327.3 362.6l94.09 94.09a25 25 0 0 0 35.3-35.3zM97.92 222.72a124.8 124.8 0 1 1 124.8 124.8a124.95 124.95 0 0 1-124.8-124.8z" fill="currentColor"></path></svg></n-icon>
                    </template>
                  </n-input>
                </div>
                <div class="history-list-scroll">
                  <div
                    v-for="task in orderedTasks"
                    :key="task.task_id"
                    class="history-item"
                    :class="{ active: state.selectedTaskId.value === task.task_id }"
                    @click="selectTask(task)"
                  >
                    <div class="history-item-header">
                      <span class="history-item-title">{{ buildTaskDisplayTitle(task) }}</span>
                    </div>
                    <div class="history-item-meta">
                      <n-tag size="small" round :bordered="false" type="info">{{ task.kind }}</n-tag>
                      <n-tag size="small" round :bordered="false" :type="statusTypeMap[task.status] || 'default'">{{ task.status ? String(task.status).toUpperCase() : 'UNKNOWN' }}</n-tag>
                      <n-text depth="3" class="font-mono" style="margin-left: auto;">{{ task.task_id.substring(0, 8) }}</n-text>
                    </div>
                  </div>
                  <n-empty v-if="!orderedTasks.length" description="暂无任务" style="margin-top: 40px;" />
                </div>
              </div>
            </n-layout-sider>
            <n-layout-content style="padding-left: 16px; background: transparent;">
              <div v-if="taskDetail" class="task-detail-pane">
                <n-descriptions bordered column="1" size="small" label-placement="left">
                  <n-descriptions-item label="任务标题">{{ taskDetail.title || '-' }}</n-descriptions-item>
                  <n-descriptions-item label="任务 ID"><n-text class="font-mono">{{ taskDetail.task_id }}</n-text></n-descriptions-item>
                  <n-descriptions-item label="任务类型"><n-tag size="small" type="info" :bordered="false">{{ taskDetail.kind }}</n-tag></n-descriptions-item>
                  <n-descriptions-item label="当前状态"><n-tag size="small" :bordered="false" :type="statusTypeMap[taskDetail.status] || 'default'">{{ String(taskDetail.status).toUpperCase() }}</n-tag></n-descriptions-item>
                  <n-descriptions-item label="目标设备">{{ taskDetail.target || '-' }}</n-descriptions-item>
                  <n-descriptions-item label="错误信息" v-if="taskDetail.error"><n-text type="error">{{ taskDetail.error }}</n-text></n-descriptions-item>
                  <n-descriptions-item label="执行结果" v-if="taskDetail.result">{{ taskDetail.result }}</n-descriptions-item>
                </n-descriptions>
                
                <div style="margin-top: 16px;">
                  <n-space>
                    <n-button type="error" secondary @click="actions.stopTask(taskDetail.task_id, taskDetail.kind)" :disabled="!taskDetail.capabilities?.can_stop">停止任务</n-button>
                    <n-button type="error" secondary @click="actions.removeTask(taskDetail.task_id)" :disabled="!taskDetail.capabilities?.can_remove">删除记录</n-button>
                    <n-button type="info" secondary @click="activeTab = 'task-output'" :disabled="taskDetail.kind !== 'script'">查看输出</n-button>
                    <n-button type="info" secondary @click="activeTab = 'task-log'" :disabled="taskDetail.kind !== 'script'">查看日志</n-button>
                  </n-space>
                </div>
              </div>
              <n-empty v-else description="未选择任务或任务详情加载中" style="margin-top: 40px;" />
            </n-layout-content>
          </n-layout>
        </n-tab-pane>

        <n-tab-pane name="task-output" tab="任务输出">
          <div style="display: flex; flex-direction: column; height: 100%; gap: 12px;">
            <div style="flex: 1; min-height: 0; border: 1px solid var(--n-border-color); border-radius: 4px; overflow: hidden; background: var(--n-color-embedded);">
              <n-log :log="outputText" style="height: 100%; padding: 12px;" />
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="task-log" tab="任务日志">
          <div style="display: flex; flex-direction: column; height: 100%; gap: 12px;">
            <div class="task-log-shell">
              <n-scrollbar x-scrollable>
                <div class="task-log-list">
                  <div
                    v-for="(log, index) in taskLogs"
                    :key="index"
                    class="task-log-item"
                    :class="`level-${getLevelType(log.level)}`"
                  >
                    <div class="task-log-meta">
                      <span class="task-log-level" :class="`text-${getLevelType(log.level)}`">{{ log.level || 'INFO' }}</span>
                    </div>
                    <pre class="task-log-message">{{ log.message }}</pre>
                  </div>
                  <n-empty v-if="!taskLogs.length" description="暂无日志记录" style="margin-top: 40px;" />
                </div>
              </n-scrollbar>
            </div>
          </div>
        </n-tab-pane>

      </n-tabs>
    </div>
  </n-card>
</template>

<style scoped>
.task-tab-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.task-manager-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.task-manager-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
}

.task-manager-tabs :deep(.n-tab-pane) {
  height: 100%;
  padding: 12px 0 0 0;
  display: flex;
  flex-direction: column;
}

.history-list-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 12px;
}

.history-item {
  border-radius: 6px;
  margin-bottom: 8px;
  padding: 10px;
  border: 1px solid var(--n-border-color);
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s, box-shadow 0.2s;
  background-color: transparent;
}

.history-item:hover {
  background-color: var(--n-color-active) !important;
}

.history-item.active {
  background-color: color-mix(in srgb, var(--n-primary-color) 10%, transparent) !important;
  border-color: var(--n-primary-color);
  box-shadow: inset 4px 0 0 0 var(--n-primary-color);
}

.history-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.history-item-title {
  font-weight: 500;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  background-color: color-mix(in srgb, var(--n-text-color) 6%, transparent);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.task-detail-pane {
  display: flex;
  flex-direction: column;
}

.task-log-shell {
  flex: 1;
  min-height: 0;
  background: var(--n-color-embedded);
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
}

.task-log-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-log-list :deep(.n-empty__description), .task-log-list :deep(.n-empty__icon) {
  color: #858585;
}

.task-log-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  border: none;
  background: transparent;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.task-log-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.task-log-item.level-error {
  background: rgba(244, 135, 113, 0.1);
}

.task-log-item.level-warning {
  background: rgba(204, 167, 0, 0.1);
}

.task-log-meta {
  display: contents;
}

.task-log-level {
  display: inline-flex;
  min-width: 48px;
  font-size: 13px;
  font-weight: bold;
  text-transform: uppercase;
}

.text-info {
  color: #3b8eea;
}

.text-error {
  color: #f48771;
}

.text-warning {
  color: #cca700;
}

.task-log-message {
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

.task-log-item.level-error .task-log-message {
  color: #f48771;
}

.task-log-item.level-warning .task-log-message {
  color: #cca700;
}
</style>
