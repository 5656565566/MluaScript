import { apiGet, apiPatch, apiPost, apiPut, buildUrl, request } from './client'

export const projectApi = {
  async listProjects() {
    return await apiGet('/api/projects')
  },

  async createProject(payload) {
    return await apiPost('/api/projects', payload)
  },

  async updateProject(projectKey, payload) {
    return await apiPatch(`/api/projects/${encodeURIComponent(projectKey)}`, payload)
  },

  async openProject(projectKey) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}:open`, {})
  },

  async listTree(projectKey) {
    return await apiGet(`/api/projects/${encodeURIComponent(projectKey)}/tree`)
  },

  async listModules(projectKey) {
    return await apiGet(`/api/projects/${encodeURIComponent(projectKey)}/modules`)
  },

  async readFile(projectKey, path) {
    return await apiGet(`/api/projects/${encodeURIComponent(projectKey)}/files/content`, { path })
  },

  async writeFile(projectKey, payload) {
    return await apiPut(`/api/projects/${encodeURIComponent(projectKey)}/files/content`, payload)
  },

  async createFile(projectKey, payload) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}/files`, payload)
  },

  async deleteFile(projectKey, path) {
    return await request(`/api/projects/${encodeURIComponent(projectKey)}/files`, {
      method: 'DELETE',
      query: { path },
    })
  },

  async createDirectory(projectKey, payload) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}/directories`, payload)
  },

  async renamePath(projectKey, payload) {
    return await apiPatch(`/api/projects/${encodeURIComponent(projectKey)}/tree`, payload)
  },

  async movePath(projectKey, payload) {
    return await apiPatch(`/api/projects/${encodeURIComponent(projectKey)}/tree:move`, payload)
  },

  async uploadFile(projectKey, path, file, overwrite = false) {
    return await request(`/api/projects/${encodeURIComponent(projectKey)}/files/binary`, {
      method: 'PUT',
      query: { path, overwrite },
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    })
  },

  fileDownloadUrl(projectKey, path) {
    return buildUrl(`/api/projects/${encodeURIComponent(projectKey)}/files/raw`, { path })
  },

  async validate(projectKey) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}/validate`, {})
  },

  async build(projectKey, payload = {}) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}/build`, payload)
  },

  async debug(projectKey, payload = {}) {
    return await apiPost(`/api/projects/${encodeURIComponent(projectKey)}/debug`, payload)
  },

  async getTemplate(projectKey, path) {
    return await apiGet(`/api/projects/${encodeURIComponent(projectKey)}/template`, { path })
  },
}
