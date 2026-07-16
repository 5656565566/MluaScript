import { apiGet, apiPost } from './client'

export const templateApi = {
  async getScriptTemplate(scriptPath) {
    return await apiGet('/api/system/scripts/template', { scriptPath })
  },
  async runWorkflow(payload) {
    return await apiPost('/api/run/lua/template', payload)
  },
}

