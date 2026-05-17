export class ApiError extends Error {
  constructor(message, options = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? 0
    this.code = options.code ?? ''
    this.data = options.data ?? null
    this.response = options.response ?? null
  }
}

const DEFAULT_HEADERS = {
  Accept: 'application/json',
}

function buildUrl(path, query) {
  const url = new URL(path, window.location.origin)
  if (query && typeof query === 'object') {
    for (const [key, value] of Object.entries(query)) {
      if (value === null || typeof value === 'undefined' || value === '') continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function parseResponseBody(response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return await response.json().catch(() => ({}))
  }
  const text = await response.text().catch(() => '')
  return text || null
}

function createApiError(response, data) {
  const detail = typeof data === 'object' && data !== null
    ? (data.detail || data.message || data.error)
    : data
  return new ApiError(detail || `HTTP ${response.status}`, {
    status: response.status,
    code: typeof data === 'object' && data !== null ? (data.code || '') : '',
    data,
    response,
  })
}

function unwrapApiEnvelope(data) {
  if (data && typeof data === 'object' && 'ok' in data && 'data' in data) {
    if (data.ok === false) {
      throw new ApiError(data.message || 'API request failed', {
        status: 200,
        code: typeof data.error === 'object' && data.error ? (data.error.code || '') : '',
        data,
        response: null,
      })
    }
    return data.data
  }
  return data
}

export async function request(path, options = {}) {
  const {
    method = 'GET',
    query,
    headers = {},
    body,
    signal,
    responseType = 'json',
  } = options

  const requestHeaders = {
    ...DEFAULT_HEADERS,
    ...headers,
  }

  const fetchOptions = {
    method,
    headers: requestHeaders,
    signal,
  }

  if (typeof body !== 'undefined') {
    fetchOptions.body = body
  }

  const response = await fetch(buildUrl(path, query), fetchOptions)

  if (responseType === 'raw') {
    if (!response.ok) {
      const errorData = await parseResponseBody(response)
      throw createApiError(response, errorData)
    }
    return response
  }

  const data = await parseResponseBody(response)
  if (!response.ok) {
    throw createApiError(response, data)
  }
  return unwrapApiEnvelope(data)
}

export async function apiGet(path, queryOrOptions = {}) {
  const options = queryOrOptions && ('query' in queryOrOptions || 'headers' in queryOrOptions || 'signal' in queryOrOptions || 'responseType' in queryOrOptions)
    ? queryOrOptions
    : { query: queryOrOptions }
  return await request(path, {
    ...options,
    method: 'GET',
  })
}

export async function apiPost(path, payload, options = {}) {
  const isFormData = typeof FormData !== 'undefined' && payload instanceof FormData
  const headers = {
    ...(options.headers || {}),
  }

  let body = payload
  if (!isFormData) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
    body = JSON.stringify(payload ?? {})
  }

  return await request(path, {
    ...options,
    method: 'POST',
    headers,
    body,
  })
}

export async function apiPut(path, payload, options = {}) {
  const headers = {
    ...(options.headers || {}),
    'Content-Type': (options.headers || {})['Content-Type'] || 'application/json',
  }
  return await request(path, {
    ...options,
    method: 'PUT',
    headers,
    body: JSON.stringify(payload ?? {}),
  })
}

export const systemApi = {
  async getBootstrap() {
    return await apiGet('/api/system/bootstrap')
  },
  async getHealth() {
    return await apiGet('/api/system/health')
  },
  async listTasks() {
    return await apiGet('/api/system/tasks')
  },
  async listScripts() {
    return await apiGet('/api/system/scripts')
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

export const templateApi = {
  async getScriptTemplate(scriptPath) {
    return await apiGet('/api/system/scripts/template', { scriptPath })
  },
  async runWorkflow(payload) {
    return await apiPost('/api/run/lua/template', payload)
  },
}

export const logApi = {
  async list(params = {}) {
    return await apiGet('/api/logs', params)
  },
}

export const streamApi = {
  createLogsStream(params = {}) {
    const url = buildUrl('/api/streams/logs', params)
    return new EventSource(url)
  },
}
