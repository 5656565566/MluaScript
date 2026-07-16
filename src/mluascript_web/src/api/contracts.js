function asArray(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeDeviceItem(item = {}) {
  return {
    id: String(item.id || ''),
    kind: String(item.kind || ''),
    name: String(item.name ?? item.title ?? ''),
    address: String(item.address ?? item.subtitle ?? ''),
    enabled: item.enabled !== false,
    tags: asArray(item.tags),
    handle: item.handle ?? item.hwnd ?? null,
  }
}

export function normalizeDeviceItems(items) {
  return asArray(items).map(normalizeDeviceItem)
}

export function normalizeDesktopItem(item = {}) {
  const normalized = normalizeDeviceItem(item)
  const handle = normalized.handle ?? normalized.address
  return {
    ...normalized,
    window_name: normalized.name,
    hwnd: handle,
    handle,
    subtitle: normalized.address,
  }
}

export function normalizeDesktopItems(items) {
  return asArray(items).map(normalizeDesktopItem)
}

export function normalizeConnection(connection = {}) {
  return {
    ...connection,
    label: String(connection.label || ''),
    connected: Boolean(connection.connected),
    canScreencap: Boolean(connection.canScreencap ?? connection.can_screencap),
  }
}

export function normalizeConnectionList(connection) {
  const normalized = normalizeConnection(connection)
  return normalized.label ? [normalized] : []
}

