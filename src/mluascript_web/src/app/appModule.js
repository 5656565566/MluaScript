import { buildWebPreferences, COLOR_THEMES, DEFAULT_CUSTOM_COLOR } from './preferences.js'
import { applyThemeVariables, isDarkTheme } from './theme.js'

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
  let preferenceSaveTimer = null
  let preferenceSaveQueue = Promise.resolve()
  let lastSavedPreferences = ''

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
    actions.closeProject?.()
    if (state.projects) state.projects.value = []
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
    if (state.preferencesHydrated?.value) {
      lastSavedPreferences = JSON.stringify(buildWebPreferences(state))
    }
    actions.applyTheme()
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
      try {
        await getActions().flushPreferences()
      } catch (error) {
        console.error(error)
      }
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

    applyTheme(
      themeValue = state.appTheme.value,
      colorTheme = state.colorTheme?.value || 'classic',
      customColor = state.customColor?.value || DEFAULT_CUSTOM_COLOR,
    ) {
      const resolvedTheme = ['system', 'light', 'dark'].includes(themeValue)
        ? themeValue
        : state.appTheme.value
      const resolvedColorTheme = COLOR_THEMES.includes(colorTheme)
        ? colorTheme
        : COLOR_THEMES.includes(state.colorTheme?.value)
          ? state.colorTheme.value
          : 'classic'
      state.appTheme.value = resolvedTheme
      if (state.colorTheme) state.colorTheme.value = resolvedColorTheme
      if (state.customColor) state.customColor.value = customColor
      const isDark = isDarkTheme(resolvedTheme, browserWindow)
      browserDocument.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
      browserDocument.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
      applyThemeVariables(browserDocument, resolvedColorTheme, customColor, isDark)
      if (state.blocklyEditor.value) updateBlocklyTheme(state.blocklyEditor.value, isDark)
      browserWindow.dispatchEvent(new Event('resize'))
    },

    schedulePreferencesSave() {
      if (!state.preferencesHydrated?.value || !state.authenticated.value) return
      if (preferenceSaveTimer) browserWindow.clearTimeout?.(preferenceSaveTimer)
      preferenceSaveTimer = browserWindow.setTimeout(() => {
        preferenceSaveTimer = null
        void getActions().flushPreferences().catch((error) => {
          getActions().setStatus(error?.message || '保存 Web 偏好设置失败', 'error')
        })
      }, 300)
    },

    flushPreferences() {
      if (preferenceSaveTimer) {
        browserWindow.clearTimeout?.(preferenceSaveTimer)
        preferenceSaveTimer = null
      }
      if (!state.preferencesHydrated?.value || !state.authenticated.value) return preferenceSaveQueue
      const payload = buildWebPreferences(state)
      const serialized = JSON.stringify(payload)
      if (serialized === lastSavedPreferences) return preferenceSaveQueue
      const save = async () => {
        await systemApi.putPreferences(payload)
        lastSavedPreferences = serialized
      }
      preferenceSaveQueue = preferenceSaveQueue.then(save, save)
      return preferenceSaveQueue
    },

    async saveCroppedImage(filename, imageBase64, directory = 'resources/assets') {
      const actions = getActions()
      const cleanBase64 = String(imageBase64 || '').replace(/^data:image\/[a-zA-Z0-9+]+;base64,/, '')
      const cleanName = String(filename || '').trim().replace(/[\\/:*?"<>|]/g, '_') || 'template.png'
      const cleanDirectory = String(directory || '').trim().replaceAll('\\', '/').replace(/^\/+|\/+$/g, '')
      if (!cleanDirectory || cleanDirectory.split('/').some(segment => !segment || segment === '.' || segment === '..')) {
        throw new Error('裁切图片保存目录无效')
      }
      const projectKey = state.currentProject?.value?.key || ''
      if (!projectKey) {
        actions.setStatus('请先打开一个项目后再保存裁切图片', 'warning')
        throw new Error('当前未打开任何项目')
      }
      if (!cleanBase64) {
        throw new Error('裁切图片数据为空')
      }
      const raw = atob(cleanBase64)
      const bytes = new Uint8Array(raw.length)
      for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
      const blob = new Blob([bytes], { type: 'image/png' })
      const targetPath = `${cleanDirectory}/${cleanName}`
      await actions.uploadProjectFile(targetPath, blob, true)
      return { path: targetPath }
    },
  }
}
