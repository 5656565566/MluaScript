const DEFAULT_COLOR_THEME = 'classic'
const DEFAULT_CUSTOM_COLOR = '#18a058'
const COLOR_THEMES = ['classic', 'emerald', 'blue', 'violet', 'amber', 'red', 'cyan', 'custom']

function valueOr(value, fallback) {
  return value === null || typeof value === 'undefined' ? fallback : value
}

function oneOf(value, allowed, fallback) {
  return allowed.includes(value) ? value : fallback
}

function customColor(value) {
  const color = String(valueOr(value, DEFAULT_CUSTOM_COLOR)).trim()
  return /^#[0-9a-f]{6}$/i.test(color) ? color.toLowerCase() : DEFAULT_CUSTOM_COLOR
}

function projectTreeWidth(value) {
  const width = Number(value)
  return Number.isFinite(width) ? Math.max(200, Math.min(420, Math.round(width))) : 240
}

export function applyWebPreferences(state, preferences = {}) {
  const appearance = preferences.appearance || {}
  const editor = preferences.editor || {}
  const tasks = preferences.tasks || {}
  const logs = preferences.logs || {}
  const layout = preferences.layout || {}

  state.appTheme.value = oneOf(appearance.themeMode, ['system', 'light', 'dark'], 'system')
  const legacyColor = customColor(appearance.accentColor)
  state.colorTheme.value = COLOR_THEMES.includes(appearance.colorTheme)
    ? appearance.colorTheme
    : appearance.accentColor
      ? 'custom'
      : DEFAULT_COLOR_THEME
  state.customColor.value = customColor(appearance.customColor || legacyColor)
  state.autoSaveFiles.value = Boolean(valueOr(editor.autoSaveFiles, true))
  state.projectTreeVisible.value = Boolean(valueOr(editor.projectTreeVisible, true))
  state.projectTreeWidth.value = projectTreeWidth(valueOr(editor.projectTreeWidth, 240))
  state.autoRefresh.value = Boolean(valueOr(tasks.autoRefresh, true))
  state.taskManagerActiveTab.value = valueOr(tasks.activeTab, 'resource-list')
  state.runLogsAutoScroll.value = Boolean(valueOr(logs.autoScroll, true))
  state.runLogsSelectedLevel.value = valueOr(logs.selectedLevel, 'all')
  state.logOrigin.value = valueOr(logs.origin, 'runtime')
  state.sidebarCollapsed.value = Boolean(valueOr(layout.sidebarCollapsed, false))
  state.activeView.value = valueOr(layout.activeView, 'editor')
  state.preferencesHydrated.value = true
}

export function buildWebPreferences(state) {
  return {
    appearance: {
      themeMode: state.appTheme.value,
      colorTheme: state.colorTheme.value,
      customColor: state.customColor.value,
      paletteVersion: 1,
    },
    editor: {
      autoSaveFiles: state.autoSaveFiles.value,
      projectTreeVisible: state.projectTreeVisible.value,
      projectTreeWidth: state.projectTreeWidth.value,
    },
    tasks: {
      autoRefresh: state.autoRefresh.value,
      activeTab: state.taskManagerActiveTab.value,
    },
    logs: {
      autoScroll: state.runLogsAutoScroll.value,
      selectedLevel: state.runLogsSelectedLevel.value,
      origin: state.logOrigin.value,
    },
    layout: {
      sidebarCollapsed: state.sidebarCollapsed.value,
      activeView: state.activeView.value,
    },
  }
}

export { COLOR_THEMES, DEFAULT_COLOR_THEME, DEFAULT_CUSTOM_COLOR }
