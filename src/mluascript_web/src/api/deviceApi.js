import { apiGet, apiPost } from './client'

export const deviceApi = {
  async discover(kind) {
    return await apiPost('/api/device/discover', { kind })
  },
  async list(kind) {
    return await apiGet('/api/device/items', { kind })
  },
  async connect(deviceId) {
    return await apiPost('/api/device/connect', { deviceId })
  },
  async connectAdb(address) {
    return await apiPost('/api/device/adb/connect-manual', { address })
  },
  async getSession() {
    return await apiGet('/api/device/session')
  },
  async disconnect() {
    return await apiPost('/api/device/disconnect', {})
  },
  async screencap() {
    return await apiPost('/api/device/screencap', {})
  },
  async click(x, y) {
    return await apiPost('/api/device/click', { x, y })
  },
}

