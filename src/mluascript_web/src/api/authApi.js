import { apiGet, apiPost } from './client'

export const authApi = {
  async status() {
    return await apiGet('/api/auth/status')
  },
  async login(payload) {
    return await apiPost('/api/auth/login', payload)
  },
  async logout() {
    return await apiPost('/api/auth/logout', {})
  },
}

