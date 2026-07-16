import { apiGet } from './client'

export const logApi = {
  async list(params = {}) {
    return await apiGet('/api/logs', params)
  },
}

