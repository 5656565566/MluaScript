import { apiPost } from './client'

export const runApi = {
  async runLua(payload) {
    return await apiPost('/api/run/lua', payload)
  },
  async stopTask(taskId, kind = 'script') {
    return await apiPost(`/api/run/${kind}/${encodeURIComponent(taskId)}/stop`, {})
  },
  async runPipeline(payload) {
    return await apiPost('/api/run/pipeline', payload)
  },
}

