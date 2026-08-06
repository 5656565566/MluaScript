<script setup>
import { onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { NConfigProvider, NGlobalStyle, NMessageProvider, NDialogProvider, NNotificationProvider, NLayout, NLayoutContent, darkTheme } from 'naive-ui'
import { state, actions } from './store'
import { buildNaiveThemeOverrides, isDarkTheme } from './app/theme'
import { setupNaiveDiscreteApi } from './naiveDiscreteApi'
import Sidebar from './components/Sidebar.vue'
import DevicePreviewFloat from './components/DevicePreviewFloat.vue'
import ScreenshotFloat from './components/ScreenshotFloat.vue'
import ModalHost from './components/ModalHost.vue'
import TemplateEditorModal from './components/TemplateEditorModal.vue'
import LoginView from './components/LoginView.vue'
import ActiveWorkspaceView from './components/ActiveWorkspaceView.vue'

let pollTimer = null
let systemThemeQuery = null

function handleSystemThemeChange() {
  if (state.appTheme.value === 'system') actions.applyTheme()
}

function startPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = window.setInterval(() => {
    actions.pollRuntime()
  }, 5000)
}

function activateAuthenticatedApp() {
  actions.startRuntimeStreams()
  startPolling()
  actions.placeScreenshotDock()
}

const theme = computed(() => {
  const isDark = isDarkTheme(state.appTheme.value, window)
  return isDark ? darkTheme : null
})

const themeOverrides = computed(() => (
  buildNaiveThemeOverrides(
    state.colorTheme.value,
    state.customColor.value,
    isDarkTheme(state.appTheme.value, window),
  )
))

onMounted(async () => {
  setupNaiveDiscreteApi()
  try {
    actions.applyTheme()
    systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)')
    systemThemeQuery.addEventListener('change', handleSystemThemeChange)
    await actions.checkAuth()
  } catch (error) {
    console.error(error)
    state.authChecked.value = true
    actions.setStatus(error.message || '初始化页面失败')
  }
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  systemThemeQuery?.removeEventListener('change', handleSystemThemeChange)
  actions.stopRuntimeStreams()
  actions.stopSelectedTaskStreams()
  actions.stopAllDevicePreviewLoops()
  void actions.flushPreferences()
})

watch(() => [
  state.appTheme.value,
  state.colorTheme.value,
  state.customColor.value,
  state.autoSaveFiles.value,
  state.projectTreeVisible.value,
  state.projectTreeWidth.value,
  state.autoRefresh.value,
  state.taskManagerActiveTab.value,
  state.runLogsAutoScroll.value,
  state.runLogsSelectedLevel.value,
  state.logOrigin.value,
  state.sidebarCollapsed.value,
  state.activeView.value,
], () => actions.schedulePreferencesSave())

watch(() => state.authenticated.value, (authenticated) => {
  if (!authenticated) {
    if (pollTimer) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
    actions.stopRuntimeStreams()
    actions.stopSelectedTaskStreams()
    return
  }
  activateAuthenticatedApp()
})

watch(() => state.activeView.value, (activeView, previousView) => {
  if (activeView === 'editor' && previousView !== 'editor') {
    state.sidebarCollapsed.value = true
  }
}, { immediate: true })
</script>

<template>
  <n-config-provider :theme="theme" :theme-overrides="themeOverrides" style="width: 100%; height: 100%;">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
  <LoginView v-if="state.authChecked.value && !state.authenticated.value" />
  <n-layout v-else-if="state.authenticated.value" has-sider class="app-shell">
    <Sidebar />
    <div class="mobile-overlay" :class="{ 'active': !state.sidebarCollapsed.value }" @click="state.sidebarCollapsed.value = true"></div>
    <n-layout content-style="display: flex; flex-direction: column; min-height: 100vh;" class="main-content">
      <div class="mobile-header">
        <button class="mobile-menu-btn" @click="state.sidebarCollapsed.value = false">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </button>
        <span class="mobile-title">MluaScript</span>
      </div>
      <div class="editor-shell">
        <ActiveWorkspaceView />
      </div>
    </n-layout>
    <ScreenshotFloat />
    <DevicePreviewFloat />
    <ModalHost />
    <TemplateEditorModal v-if="state.templateEditorModalVisible.value" />
  </n-layout>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  min-width: 0;
}

.editor-shell {
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  width: 100%;
  flex: 1;
  min-height: 0;
}

@media (max-width: 768px) {
  .main-content {
    height: 100dvh;
  }

  .mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--color-overlay);
    z-index: 99;
    display: none;
  }

  .mobile-overlay.active {
    display: block;
  }

  .mobile-header {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    background: var(--n-color);
    border-bottom: 1px solid var(--n-border-color);
    gap: 16px;
    flex-shrink: 0;
  }

  .mobile-menu-btn {
    background: transparent;
    border: none;
    color: var(--n-text-color);
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .mobile-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--n-text-color);
  }
}

@media (min-width: 769px) {
  .mobile-header {
    display: none;
  }
}
</style>
