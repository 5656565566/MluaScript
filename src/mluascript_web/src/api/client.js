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

let unauthorizedHandler = null

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === 'function' ? handler : null
}

export function buildUrl(path, query) {
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
  const rawDetail = typeof data === 'object' && data !== null
    ? (data.detail || data.message || data.error)
    : data
  const detail = rawDetail && typeof rawDetail === 'object'
    ? (rawDetail.message || JSON.stringify(rawDetail))
    : rawDetail
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
      if (response.status === 401) unauthorizedHandler?.()
      throw createApiError(response, errorData)
    }
    return response
  }

  const data = await parseResponseBody(response)
  if (!response.ok) {
    if (response.status === 401) unauthorizedHandler?.()
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

export async function apiPatch(path, payload, options = {}) {
  const headers = {
    ...(options.headers || {}),
    'Content-Type': (options.headers || {})['Content-Type'] || 'application/json',
  }
  return await request(path, {
    ...options,
    method: 'PATCH',
    headers,
    body: JSON.stringify(payload ?? {}),
  })
}
