import { buildUrl } from './client'

export const streamApi = {
  createLogsStream(params = {}) {
    return new EventSource(buildUrl('/api/streams/logs', params))
  },
  createTaskLogsStream(taskId) {
    return new EventSource(buildUrl(`/api/streams/tasks/${encodeURIComponent(taskId)}/logs`))
  },
  createTaskOutputStream(taskId) {
    return new EventSource(buildUrl(`/api/streams/tasks/${encodeURIComponent(taskId)}/output`))
  },
}

