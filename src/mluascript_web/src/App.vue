<script setup>
import { onMounted, onBeforeUnmount, computed } from 'vue'
import { NConfigProvider, NGlobalStyle, NMessageProvider, NDialogProvider, NNotificationProvider, NLayout, NLayoutContent, darkTheme } from 'naive-ui'
import { state, actions } from './store'
import { setupNaiveDiscreteApi } from './naiveDiscreteApi'
import Sidebar from './components/Sidebar.vue'
import BlocklyView from './components/BlocklyView.vue'
import TaskManagerView from './components/TaskManagerView.vue'
import DeviceView from './components/DeviceView.vue'
import DeviceManagerView from './components/DeviceManagerView.vue'
import DevicePreviewFloat from './components/DevicePreviewFloat.vue'
import RunLogsView from './components/RunLogsView.vue'
import TemplateRunnerView from './components/TemplateRunnerView.vue'
import ScreenshotFloat from './components/ScreenshotFloat.vue'
import ModalHost from './components/ModalHost.vue'
import TemplateEditorModal from './components/TemplateEditorModal.vue'

let pollTimer = null

function startPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = window.setInterval(() => {
    actions.pollRuntime()
  }, 2000)
}

const theme = computed(() => {
  const themeValue = state.appTheme.value
  const isDark = themeValue === 'dark' || (themeValue === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  return isDark ? darkTheme : null
})

onMounted(async () => {
  setupNaiveDiscreteApi()
  try {
    await actions.loadState()
    await actions.refreshLogs()
    actions.applyTheme()
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (state.appTheme.value === 'system') actions.applyTheme()
    })
    startPolling()
    actions.placeScreenshotDock()
  } catch (error) {
    console.error(error)
    actions.setStatus(error.message || '初始化页面失败')
  }
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  actions.stopAllDevicePreviewLoops()
})
</script>

<template>
  <n-config-provider :theme="theme" style="width: 100%; height: 100%;">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
  <n-layout has-sider class="app-shell">
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
        <BlocklyView />
        <TaskManagerView />
        <TemplateRunnerView />
        <DeviceView />
        <DeviceManagerView />
        <RunLogsView />
      </div>
    </n-layout>
    <ScreenshotFloat />
    <DevicePreviewFloat />
    <ModalHost />
    <TemplateEditorModal />
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
    background: rgba(0, 0, 0, 0.5);
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
