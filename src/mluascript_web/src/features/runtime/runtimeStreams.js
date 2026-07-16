export function createRuntimeStreams({
  streamApi,
  scheduler,
  isAuthenticated,
  getSelectedTaskId,
  getLogParams,
  onLogsSnapshot,
  onLog,
  onTaskLogs,
  onTaskOutput,
  maxLogs = 2000,
}) {
  let logsStream = null
  let logsReconnectTimer = null
  let taskLogsStream = null
  let taskOutputStream = null
  let taskId = ''
  let taskReconnectTimer = null

  function close(source) {
    if (source) source.close()
  }

  function scheduleLogsReconnect() {
    if (logsReconnectTimer || !isAuthenticated()) return
    logsReconnectTimer = scheduler.setTimeout(() => {
      logsReconnectTimer = null
      startLogs()
    }, 2000)
  }

  function scheduleTaskReconnect(expectedTaskId) {
    if (taskReconnectTimer || expectedTaskId !== taskId || getSelectedTaskId() !== expectedTaskId) return
    taskReconnectTimer = scheduler.setTimeout(() => {
      taskReconnectTimer = null
      startTask(expectedTaskId)
    }, 2000)
  }

  function stopLogs() {
    close(logsStream)
    logsStream = null
    if (logsReconnectTimer) {
      scheduler.clearTimeout(logsReconnectTimer)
      logsReconnectTimer = null
    }
  }

  function startLogs() {
    stopLogs()
    if (!isAuthenticated()) return
    const source = streamApi.createLogsStream(getLogParams())
    logsStream = source
    source.addEventListener('snapshot', (event) => {
      const payload = JSON.parse(event.data || '{}')
      const items = Array.isArray(payload.items) ? payload.items.slice(-maxLogs) : []
      onLogsSnapshot(items)
    })
    source.addEventListener('log', (event) => {
      onLog(JSON.parse(event.data || '{}'), maxLogs)
    })
    source.addEventListener('heartbeat', () => {})
    source.onerror = () => {
      if (logsStream !== source) return
      close(source)
      logsStream = null
      scheduleLogsReconnect()
    }
  }

  function stopTask() {
    close(taskLogsStream)
    close(taskOutputStream)
    taskLogsStream = null
    taskOutputStream = null
    taskId = ''
    if (taskReconnectTimer) {
      scheduler.clearTimeout(taskReconnectTimer)
      taskReconnectTimer = null
    }
  }

  function startTask(nextTaskId = getSelectedTaskId()) {
    if (!nextTaskId) {
      stopTask()
      return
    }
    if (taskId === nextTaskId && taskLogsStream && taskOutputStream) return

    stopTask()
    taskId = nextTaskId
    const isCurrent = () => getSelectedTaskId() === nextTaskId && taskId === nextTaskId

    const logsSource = streamApi.createTaskLogsStream(nextTaskId)
    taskLogsStream = logsSource
    for (const eventName of ['snapshot', 'update']) {
      logsSource.addEventListener(eventName, (event) => {
        if (isCurrent()) onTaskLogs(nextTaskId, JSON.parse(event.data || '{}'))
      })
    }
    logsSource.addEventListener('not_found', () => {
      if (isCurrent()) stopTask()
    })
    logsSource.addEventListener('heartbeat', () => {})
    logsSource.onerror = () => {
      if (taskLogsStream !== logsSource) return
      close(logsSource)
      taskLogsStream = null
      scheduleTaskReconnect(nextTaskId)
    }

    const outputSource = streamApi.createTaskOutputStream(nextTaskId)
    taskOutputStream = outputSource
    for (const eventName of ['snapshot', 'update']) {
      outputSource.addEventListener(eventName, (event) => {
        if (isCurrent()) onTaskOutput(nextTaskId, JSON.parse(event.data || '{}'))
      })
    }
    outputSource.addEventListener('not_found', () => {
      if (isCurrent()) stopTask()
    })
    outputSource.addEventListener('heartbeat', () => {})
    outputSource.onerror = () => {
      if (taskOutputStream !== outputSource) return
      close(outputSource)
      taskOutputStream = null
      scheduleTaskReconnect(nextTaskId)
    }
  }

  return {
    startLogs,
    stopLogs,
    startTask,
    stopTask,
    stopAll() {
      stopLogs()
      stopTask()
    },
  }
}

