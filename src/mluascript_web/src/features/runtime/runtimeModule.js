export function createRuntimeActions({ state, systemApi, runApi, runtimeStreams, getActions }) {
  function applyTaskLogs(taskId, payload) {
    state.taskLogsById.value = {
      ...state.taskLogsById.value,
      [taskId]: payload,
    }
  }

  function applyTaskOutput(taskId, payload) {
    state.taskOutputById.value = {
      ...state.taskOutputById.value,
      [taskId]: payload,
    }
  }

  async function refreshSelectedTask() {
    const taskId = state.selectedTaskId.value
    if (!taskId) return null
    return await getActions().fetchTaskDetail(taskId)
  }

  async function refreshRuntimeSummary({ includeSelectedTask = false } = {}) {
    const [tasksPayload, scriptsPayload] = await Promise.all([
      systemApi.listTasks(),
      systemApi.listScripts(),
    ])
    state.tasks.value = tasksPayload.items || tasksPayload.data?.items || []
    state.availableScripts.value = scriptsPayload.items || []
    if (state.selectedTaskId.value && !state.tasks.value.some(item => item.task_id === state.selectedTaskId.value)) {
      runtimeStreams.stopTask()
      state.selectedTaskId.value = ''
    }
    if (!state.selectedTaskId.value && state.tasks.value.length) {
      state.selectedTaskId.value = state.tasks.value[state.tasks.value.length - 1].task_id
    }
    return includeSelectedTask ? await refreshSelectedTask() : null
  }

  return {
    applyTaskLogs,
    applyTaskOutput,
    refreshSelectedTask,

    async fetchTaskDetail(taskId) {
      if (!taskId) return null
      const data = await systemApi.getTaskDetail(taskId)
      state.taskDetailById.value = {
        ...state.taskDetailById.value,
        [taskId]: data.data || data,
      }
      return state.taskDetailById.value[taskId]
    },

    async fetchTaskLogs(taskId) {
      if (!taskId) return null
      const data = await systemApi.getTaskLogs(taskId)
      applyTaskLogs(taskId, data.data || data)
      return state.taskLogsById.value[taskId]
    },

    async fetchTaskOutput(taskId) {
      if (!taskId) return null
      const data = await systemApi.getTaskOutput(taskId)
      applyTaskOutput(taskId, data.data || data)
      return state.taskOutputById.value[taskId]
    },

    stopRuntimeStreams() {
      runtimeStreams.stopLogs()
    },

    startRuntimeStreams() {
      runtimeStreams.startLogs()
    },

    stopSelectedTaskStreams() {
      runtimeStreams.stopTask()
    },

    startSelectedTaskStreams(taskId = state.selectedTaskId.value) {
      runtimeStreams.startTask(taskId)
    },

    async removeTask(taskId) {
      if (!taskId) return
      await systemApi.removeTask(taskId)
      if (state.selectedTaskId.value === taskId) state.selectedTaskId.value = ''
      await getActions().loadState()
    },

    async stopTask(taskId, kind = 'script', { refresh = true } = {}) {
      if (!taskId) return
      await runApi.stopTask(taskId, kind)
      if (refresh) await getActions().loadState()
    },

    async refreshTaskManagerData() {
      const detail = await refreshRuntimeSummary({ includeSelectedTask: true })
      return { detail: detail || null }
    },

    async refreshLogs(logOrigin = state.logOrigin.value) {
      state.logOrigin.value = logOrigin
      runtimeStreams.startLogs()
    },

    async pollRuntime() {
      if (!state.autoRefresh.value) return
      try {
        await refreshRuntimeSummary({ includeSelectedTask: state.activeView.value === 'task-manager' })
      } catch (error) {
        console.error(error)
      }
    },

    async runLuaScript(scriptPath = null, luaCode = null, sessionLabel = state.selectedSession.value) {
      state.runtimeState.value = 'running-lua'
      try {
        const data = await runApi.runLua({
          sessionLabel: sessionLabel || null,
          luaCode: luaCode ?? state.luaCode.value ?? '',
          scriptPath: scriptPath || state.savePath.value || state.filename.value || null,
        })
        await getActions().loadState()
        getActions().setStatus(data.message || 'Lua 任务已启动', 'success')
        return data
      } finally {
        state.runtimeState.value = 'idle'
      }
    },

    async runLuaTask(sessionLabel = state.selectedSession.value, luaCode = state.luaCode.value, scriptPath = state.savePath.value || state.filename.value) {
      return await getActions().runLuaScript(scriptPath, luaCode, sessionLabel)
    },

    async stopLuaTask(taskId) {
      if (!taskId) throw new Error('缺少 taskId')
      await runApi.stopTask(taskId, 'script')
      await getActions().loadState()
      getActions().setStatus(`已停止任务: ${taskId}`, 'success')
    },

    async runPipelineTask(entry, override = {}, sessionLabel = state.selectedSession.value, projectPath = '') {
      void sessionLabel
      const data = await runApi.runPipeline({ entry, override, projectPath })
      await getActions().loadState()
      getActions().setStatus(data.message || 'Pipeline 任务已启动', 'success')
      return data
    },

    async stopTasks() {
      const runningTasks = state.tasks.value.filter((task) => task?.status === 'running' && task?.task_id)
      if (!runningTasks.length) {
        getActions().setStatus('当前没有运行中的任务', 'info')
        return
      }
      await Promise.all(runningTasks.map((task) => runApi.stopTask(task.task_id, task.kind || 'script')))
      await getActions().loadState()
      getActions().setStatus(`已停止 ${runningTasks.length} 个任务`, 'success')
    },
  }
}
