import { apiGet, apiPost, apiPut } from './client'

export const editorApi = {
  async getSession() {
    return await apiGet('/api/editor/session')
  },
  async syncSession(payload) {
    return await apiPut('/api/editor/session', payload)
  },
  async listBlocklyFiles() {
    return await apiGet('/api/editor/blockly/files')
  },
  async loadBlocklyFile(path) {
    return await apiGet('/api/editor/blockly/files/content', { path })
  },
  async createBlocklyFile(payload) {
    return await apiPost('/api/editor/blockly/files', payload)
  },
  async updateBlocklyFile(payload) {
    return await apiPut('/api/editor/blockly/files/content', payload)
  },
  async validateBlocklyName(path) {
    return await apiPost('/api/editor/blockly/files:validate-name', { path })
  },
  async listLuaFiles() {
    return await apiGet('/api/editor/lua/files')
  },
  async loadLuaFile(path) {
    return await apiGet('/api/editor/lua/files/content', { path })
  },
  async createLuaFile(payload) {
    return await apiPost('/api/editor/lua/files', payload)
  },
  async updateLuaFile(payload) {
    return await apiPut('/api/editor/lua/files/content', payload)
  },
  async validateLuaName(path) {
    return await apiPost('/api/editor/lua/files:validate-name', { path })
  },
}

