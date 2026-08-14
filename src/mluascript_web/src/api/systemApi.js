import { apiGet, apiPut, request } from './client'

export const systemApi = {
  async getBootstrap() {
    return await apiGet('/api/system/bootstrap')
  },
  async getHealth() {
    return await apiGet('/api/system/health')
  },
  async putPreferences(payload) {
    return await apiPut('/api/system/preferences', payload)
  },
  async listTasks() {
    return await apiGet('/api/system/tasks')
  },
  async listScripts() {
    return await apiGet('/api/system/scripts')
  },
  async getArtifactReadme(artifactId) {
    return await apiGet(`/api/system/scripts/${encodeURIComponent(artifactId)}/readme`)
  },
  async getArtifactTemplate(artifactId) {
    return await apiGet(`/api/system/scripts/${encodeURIComponent(artifactId)}/template`)
  },
  async getTaskDetail(taskId) {
    return await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}`)
  },
  async getTaskLogs(taskId) {
    return await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}/logs`)
  },
  async getTaskOutput(taskId) {
    return await apiGet(`/api/system/tasks/${encodeURIComponent(taskId)}/output`)
  },
  async removeTask(taskId) {
    return await request(`/api/system/tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    })
  },
}

