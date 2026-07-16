export function createDeviceActions({
  state,
  deviceApi,
  normalizeConnectionList,
  normalizeDesktopItems,
  normalizeDeviceItems,
  scheduler,
  getActions,
  now = () => Date.now(),
}) {
  const previewLoops = new Map()

  function setConnection(connection) {
    state.sessions.value = normalizeConnectionList(connection)
    state.selectedSession.value = connection?.label || ''
  }

  function createPreviewWindow(sessionLabel) {
    const offset = state.nextPreviewWindowOffset.value || 0
    state.nextPreviewWindowOffset.value = offset + 1
    return {
      id: `${sessionLabel}-${now()}-${offset}`,
      label: sessionLabel,
      imageBase64: '',
      intervalMs: Number(state.devicePreviewIntervalMs.value) || 1000,
      x: 24 + (offset % 4) * 32,
      y: 96 + (offset % 4) * 24,
    }
  }

  async function captureDevicePreviewFrame(windowId, sessionLabel) {
    if (!windowId || !sessionLabel) return
    const data = await deviceApi.screencap()
    if (!data.imageBase64 || !state.devicePreviewWindows.value.some((win) => win.id === windowId)) return
    state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) =>
      win.id === windowId ? { ...win, imageBase64: data.imageBase64 } : win
    )
  }

  function stopDevicePreviewLoop(windowId) {
    const loop = previewLoops.get(windowId)
    if (!loop) return
    loop.cancelled = true
    if (loop.timer) scheduler.clearTimeout(loop.timer)
    previewLoops.delete(windowId)
  }

  async function startDevicePreviewLoop(windowId) {
    const win = state.devicePreviewWindows.value.find((item) => item.id === windowId)
    if (!win) return
    stopDevicePreviewLoop(windowId)

    const loop = { cancelled: false, timer: null }
    previewLoops.set(windowId, loop)
    const runFrame = async () => {
      if (loop.cancelled || previewLoops.get(windowId) !== loop) return
      try {
        await captureDevicePreviewFrame(win.id, win.label)
      } catch (error) {
        console.error(error)
      }
      if (loop.cancelled || previewLoops.get(windowId) !== loop) return
      const current = state.devicePreviewWindows.value.find((item) => item.id === windowId)
      if (!current) {
        stopDevicePreviewLoop(windowId)
        return
      }
      const interval = Math.max(200, Number(current.intervalMs || state.devicePreviewIntervalMs.value) || 1000)
      loop.timer = scheduler.setTimeout(runFrame, interval)
    }
    await runFrame()
  }

  return {
    async searchAdb() {
      const data = await deviceApi.discover('adb')
      state.adbDevices.value = normalizeDeviceItems(data.items).filter((item) => item.id.startsWith('adb:'))
      getActions().setStatus(data.message || `搜索到 ${state.adbDevices.value.length} 个 ADB 设备`)
    },

    async connectAdb(address = state.adbAddress.value) {
      const result = await deviceApi.connectAdb(address)
      setConnection(result.connection)
      getActions().setStatus(result.message || `ADB 已连接: ${result.connection?.label || address}`, 'success')
    },

    async loadEmulators() {
      state.emulatorDevices.value = normalizeDeviceItems((await deviceApi.list('emulator')).items)
      getActions().setStatus(`已加载 ${state.emulatorDevices.value.length} 个模拟器配置`)
    },

    async loadBrowsers() {
      state.browserDevices.value = normalizeDeviceItems((await deviceApi.list('browser')).items)
      getActions().setStatus(`已加载 ${state.browserDevices.value.length} 个浏览器配置`)
    },

    async connectEmulator(deviceRef) {
      const device = state.emulatorDevices.value.find((item) => item.id === deviceRef || String(item.address || '') === String(deviceRef))
      if (!device?.id) throw new Error('未找到对应模拟器设备')
      const result = await deviceApi.connect(device.id)
      setConnection(result.connection)
      getActions().setStatus(result.message || `模拟器已连接: ${result.connection?.label || device.address || deviceRef}`, 'success')
    },

    async connectBrowser(deviceId) {
      if (!deviceId) throw new Error('未找到对应浏览器设备')
      const result = await deviceApi.connect(deviceId)
      setConnection(result.connection)
      getActions().setStatus(result.message || `浏览器已连接: ${result.connection?.label || deviceId}`, 'success')
    },

    async searchWin32() {
      const data = await deviceApi.discover('desktop')
      state.win32Windows.value = normalizeDesktopItems(data.items)
        .filter((item) => item.id.startsWith('desktop:'))
      getActions().setStatus(data.message || `搜索到 ${state.win32Windows.value.length} 个本地窗口`)
    },

    async connectWin32(hwnd) {
      const normalizedHwnd = String(hwnd || '').trim()
      const device = state.win32Windows.value.find((item) => {
        const candidates = [item.id, item.hwnd, item.handle, item.subtitle]
          .filter(Boolean)
          .map((value) => String(value))
        return candidates.some((value) => value === normalizedHwnd || value.includes(normalizedHwnd))
      })
      if (!device?.id) throw new Error('未找到对应本地窗口')
      const result = await deviceApi.connect(device.id)
      setConnection(result.connection)
      getActions().setStatus(result.message || `本地窗口已连接: ${result.connection?.label || hwnd}`, 'success')
    },

    async reloadSessions() {
      const data = await deviceApi.getSession()
      state.sessions.value = normalizeConnectionList(data.item)
      if (state.selectedSession.value && !state.sessions.value.some((session) => session.label === state.selectedSession.value)) {
        state.selectedSession.value = ''
      }
      if (state.sessions.value.length && !state.selectedSession.value) {
        state.selectedSession.value = state.sessions.value[0].label
      }
    },

    async disconnectSession(label = state.selectedSession.value) {
      void label
      const data = await deviceApi.disconnect()
      state.sessions.value = (data.sessions || [])
        .map((item) => normalizeConnectionList(item)[0])
        .filter(Boolean)
      state.selectedSession.value = state.sessions.value[0]?.label || ''
      getActions().stopAllDevicePreviewLoops()
      state.devicePreviewWindows.value = []
      getActions().setStatus(data.message || '设备已断开', 'success')
    },

    async doScreencap() {
      if (!state.selectedSession.value) throw new Error('请先选择一个连接的设备')
      const data = await deviceApi.screencap()
      getActions().setStatus(data.message || '截图成功', 'success')
      if (data.imageBase64) {
        state.screenshotBase64.value = data.imageBase64
        state.showScreenshot.value = true
        state.screenshotPath.value = '截图时间：' + new Date().toLocaleTimeString()
      }
    },

    captureDevicePreviewFrame,
    startDevicePreviewLoop,
    stopDevicePreviewLoop,

    stopAllDevicePreviewLoops() {
      for (const windowId of [...previewLoops.keys()]) {
        stopDevicePreviewLoop(windowId)
      }
    },

    async openDevicePreviewWindow() {
      if (!state.selectedSession.value) throw new Error('请先选择一个连接的设备')
      const win = createPreviewWindow(state.selectedSession.value)
      state.devicePreviewWindows.value = [...state.devicePreviewWindows.value, win]
      await startDevicePreviewLoop(win.id)
    },

    closeDevicePreviewWindow(windowId) {
      stopDevicePreviewLoop(windowId)
      state.devicePreviewWindows.value = state.devicePreviewWindows.value.filter((item) => item.id !== windowId)
    },

    updateDevicePreviewWindowPosition(windowId, x, y) {
      state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) =>
        win.id === windowId
          ? { ...win, x: Math.max(0, Math.round(x)), y: Math.max(0, Math.round(y)) }
          : win
      )
    },

    setDevicePreviewInterval(intervalMs) {
      const next = Number(intervalMs) || 1000
      state.devicePreviewIntervalMs.value = next
      state.devicePreviewWindows.value = state.devicePreviewWindows.value.map((win) => ({
        ...win,
        intervalMs: next,
      }))
      state.devicePreviewWindows.value.forEach((win) => {
        startDevicePreviewLoop(win.id).catch((error) => console.error(error))
      })
    },
  }
}
