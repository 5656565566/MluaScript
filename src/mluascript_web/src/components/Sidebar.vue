<script setup>
import { h, computed } from 'vue'
import { NLayoutSider, NMenu, NCheckbox, NSelect, NButton, NIcon, NDivider, NTooltip } from 'naive-ui'
import { state, actions } from '../store'

function renderIcon(svgContent) {
  return () => h(NIcon, null, { default: () => h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'strokeWidth': '2', 'strokeLinecap': 'round', 'strokeLinejoin': 'round', innerHTML: svgContent }) })
}

const menuOptions = [
  { label: 'Blockly', key: 'blockly', icon: renderIcon('<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/>') },
  { label: '任务管理', key: 'task-manager', icon: renderIcon('<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>') },
  { label: '模板执行', key: 'template-runner', icon: renderIcon('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><rect width="8" height="8" x="13" y="3" rx="1"/><path d="M7 12h10"/><path d="M7 16h7"/>') },
  { label: '设备连接', key: 'device', icon: renderIcon('<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>') },
  { label: '设备管理', key: 'device-manager', icon: renderIcon('<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M2 12h2"/><path d="M20 12h2"/>') },
  { label: '系统日志', key: 'run-logs', icon: renderIcon('<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M13 2v7h7"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M8 9h2"/>') }
]

const themeOptions = [
  { label: '跟随系统主题', value: 'system' },
  { label: '亮色主题', value: 'light' },
  { label: '暗色主题', value: 'dark' }
]

const collapsed = computed({
  get: () => state.sidebarCollapsed.value,
  set: (val) => state.sidebarCollapsed.value = val
})

const activeKey = computed({
  get: () => state.activeView.value,
  set: (val) => state.activeView.value = val
})
</script>

<template>
  <n-layout-sider
    bordered
    collapse-mode="width"
    :collapsed-width="64"
    :width="240"
    :collapsed="collapsed"
    show-trigger
    @collapse="collapsed = true"
    @expand="collapsed = false"
    class="sidebar"
    :class="{ 'mobile-hidden': collapsed && isMobile }"
  >
    <div style="display: flex; flex-direction: column; height: 100%;">
      <div style="display: flex; align-items: center; justify-content: center; height: 64px; flex-shrink: 0; gap: 12px; overflow: hidden;">
        <img src="/favicon.ico" alt="Logo" style="width: 32px; height: 32px;" />
        <h1 v-show="!collapsed" style="margin: 0; font-size: 18px; font-weight: 600; white-space: nowrap;">MluaScript</h1>
      </div>
      
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="22"
        :options="menuOptions"
        v-model:value="activeKey"
        style="flex: 1;"
      />

      <n-divider style="margin: 0;" />

      <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px; flex-shrink: 0;">
        <template v-if="!collapsed">
          <n-checkbox v-model:checked="state.autoRefresh.value">自动刷新</n-checkbox>
          <n-checkbox v-model:checked="state.autoSaveBlockly.value">自动保存 Blockly</n-checkbox>
          <n-button quaternary @click="state.showScreenshot.value = !state.showScreenshot.value" style="justify-content: flex-start; padding: 0 8px;">
            <template #icon>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19V7a2 2 0 0 0-2-2h-4l-2-2H9L7 5H3a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h18a2 2 0 0 0 2-2z"/><circle cx="12" cy="13" r="4"/></svg></n-icon>
            </template>
            {{ state.showScreenshot.value ? '关闭截图预览' : '打开截图预览' }}
          </n-button>
          
          <n-button quaternary @click="actions.toggleFullscreen()" style="justify-content: flex-start; padding: 0 8px;">
            <template #icon>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg></n-icon>
            </template>
            全屏模式
          </n-button>

          <n-select v-model:value="state.appTheme.value" :options="themeOptions" @update:value="actions.applyTheme" size="small" />
        </template>
        <template v-else>
          <n-tooltip placement="right" trigger="hover">
            <template #trigger>
              <n-button circle quaternary @click="collapsed = false" style="margin: 0 auto; display: flex;">
                <template #icon>
                  <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></n-icon>
                </template>
              </n-button>
            </template>
            设置
          </n-tooltip>
        </template>
      </div>
    </div>
  </n-layout-sider>
</template>

<style scoped>
.sidebar {
  height: 100vh;
  z-index: 100;
}
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 1000;
    transition: transform 0.3s ease;
  }
  .mobile-hidden {
    transform: translateX(-100%);
  }
}
</style>
