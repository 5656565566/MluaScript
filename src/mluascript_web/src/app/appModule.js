export function createAppActions({
  state,
  authApi,
  editorApi,
  logApi,
  systemApi,
  applyBootstrap,
  updateBlocklyTheme,
  browserWindow,
  browserDocument,
  getActions,
}) {
  let lifecycleGeneration = 0

  function markFeatureUnavailable(name) {
    throw new Error(`${name} 暂未实现`)
  }

  function clearAuthenticatedState() {
    const actions = getActions()
    state.authenticated.value = false
    state.currentUser.value = ''
    actions.invalidateEditorOperations()
    actions.stopRuntimeStreams()
    actions.stopSelectedTaskStreams()
    actions.stopAllDevicePreviewLoops()
    void actions.closeTemplateEditor?.()
    state.editorSessionHydrated.value = false
    state.lastSessionBlocklyXml.value = ''
    state.lastSessionBlocklyFilename.value = ''
    state.lastSessionBlocklyPath.value = ''
    state.lastSessionLuaCode.value = ''
    state.lastSessionLuaFilename.value = ''
    state.lastSessionLuaPath.value = ''
    state.tasks.value = []
    state.logs.value = []
  }

  async function loadState({ startStreams = true, generation = lifecycleGeneration } = {}) {
    const [bootstrap, logData, luaFilesPayload, tasksPayload, scriptsPayload] = await Promise.all([
      systemApi.getBootstrap(),
      logApi.list(state.logOrigin.value ? { channel: state.logOrigin.value } : {}),
      editorApi.listLuaFiles(),
      systemApi.listTasks(),
      systemApi.listScripts(),
    ])
    if (generation !== lifecycleGeneration) return false

    const actions = getActions()
    const editorHydration = applyBootstrap(bootstrap)
    state.logs.value = logData.items || []
    state.luaFiles.value = luaFilesPayload.items || []
    state.tasks.value = tasksPayload.items || []
    state.availableScripts.value = scriptsPayload.items || []
    if (editorHydration.blocklyApplied && state.blocklyEditor.value) {
      await actions.applyHydratedBlocklyWorkspace()
    }
    if (state.activeView.value === 'task-manager') {
      await actions.refreshSelectedTask()
    }
    if (startStreams) {
      actions.startRuntimeStreams()
    }
    return true
  }

  return {
    async checkAuth() {
      const generation = lifecycleGeneration
      const data = await authApi.status()
      const authenticated = Boolean(data.authenticated)
      if (authenticated) await loadState({ startStreams: false, generation })
      if (generation !== lifecycleGeneration) return false
      state.authenticated.value = authenticated
      state.currentUser.value = data.username || ''
      state.authChecked.value = true
      return authenticated
    },

    async login(username, password) {
      const generation = lifecycleGeneration
      const data = await authApi.login({ username, password })
      const authenticated = Boolean(data.authenticated)
      if (authenticated) await loadState({ startStreams: false, generation })
      if (generation !== lifecycleGeneration) return
      state.authenticated.value = authenticated
      state.currentUser.value = data.username || username
      state.authChecked.value = true
      getActions().setStatus('登录成功', 'success')
    },

    async logout() {
      lifecycleGeneration += 1
      clearAuthenticatedState()
      await authApi.logout()
      getActions().setStatus('已退出登录', 'info')
    },

    handleUnauthorized() {
      if (!state.authenticated.value) return
      lifecycleGeneration += 1
      clearAuthenticatedState()
      getActions().setStatus('登录状态已失效，请重新登录', 'warning')
    },

    setStatus(text, type = 'info') {
      state.statusText.value = text
      const messageApi = browserWindow.$message
      if (!messageApi) return
      if (type === 'error') messageApi.error(text)
      else if (type === 'success') messageApi.success(text)
      else if (type === 'warning') messageApi.warning(text)
      else messageApi.info(text)
    },

    async handleAction(handler) {
      state.pendingActionCount.value += 1
      state.loading.value = true
      try {
        return await handler()
      } catch (error) {
        console.error(error)
        getActions().setStatus(error.message || '操作失败', 'error')
        throw error
      } finally {
        state.pendingActionCount.value = Math.max(0, state.pendingActionCount.value - 1)
        state.loading.value = state.pendingActionCount.value > 0
      }
    },

    toggleFullscreen() {
      if (!browserDocument.fullscreenElement) browserDocument.documentElement.requestFullscreen?.()
      else browserDocument.exitFullscreen?.()
    },

    placeScreenshotDock() {
      state.screenshotPosition.value = {
        x: Math.max(16, browserWindow.innerWidth - 360),
        y: 96,
      }
    },

    loadState,

    async initFramework() {
      markFeatureUnavailable('MaaFramework 初始化')
    },

    applyTheme(themeValue = state.appTheme.value) {
      state.appTheme.value = themeValue
      const isDark = themeValue === 'dark' || (themeValue === 'system' && browserWindow.matchMedia('(prefers-color-scheme: dark)').matches)
      browserDocument.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
      browserDocument.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
      if (state.blocklyEditor.value) updateBlocklyTheme(state.blocklyEditor.value, isDark)
      browserWindow.dispatchEvent(new Event('resize'))
    },

    async saveCroppedImage(filename, imageBase64) {
      void filename
      void imageBase64
      markFeatureUnavailable('裁切图片保存')
    },
  }
}
