<script setup>
import { h, computed } from 'vue'
import { NLayoutSider, NMenu, NSelect, NButton, NIcon, NDivider, NTooltip, NColorPicker, NText } from 'naive-ui'
import { state, actions } from '../store'
import { COLOR_THEME_OPTIONS, colorThemePreview, isDarkTheme } from '../app/theme'

function renderIcon(svgContent) {
  return () => h(NIcon, null, { default: () => h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'strokeWidth': '2', 'strokeLinecap': 'round', 'strokeLinejoin': 'round', innerHTML: svgContent }) })
}

const menuOptions = [
  { label: '编辑器', key: 'editor', icon: renderIcon('<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 9h18"/><path d="M9 13h6"/><path d="M9 16h4"/>') },
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

function applyAppTheme(value) {
  actions.applyTheme(value, state.colorTheme.value, state.customColor.value)
}

function applyColorTheme(value) {
  actions.applyTheme(state.appTheme.value, value, state.customColor.value)
}

function applyCustomColor(value) {
  actions.applyTheme(state.appTheme.value, 'custom', value)
}

function paletteStyle(value) {
  return {
    background: colorThemePreview(
      value,
      state.customColor.value,
      isDarkTheme(state.appTheme.value, window),
    ),
  }
}

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
          <n-button quaternary @click="actions.toggleFullscreen()" style="justify-content: flex-start; padding: 0 8px;">
            <template #icon>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg></n-icon>
            </template>
            全屏模式
          </n-button>

          <n-button quaternary @click="actions.logout()" style="justify-content: flex-start; padding: 0 8px;">
            <template #icon>
              <n-icon><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg></n-icon>
            </template>
            退出登录
          </n-button>

          <n-select v-model:value="state.appTheme.value" :options="themeOptions" @update:value="applyAppTheme" size="small" />
          <div class="color-theme-picker">
            <n-text depth="3" class="color-theme-label">颜色主题</n-text>
            <div class="color-theme-grid" role="radiogroup" aria-label="颜色主题">
              <button
                v-for="option in COLOR_THEME_OPTIONS"
                :key="option.value"
                type="button"
                class="color-theme-option"
                :class="{ active: state.colorTheme.value === option.value }"
                :title="option.label"
                :aria-label="option.label"
                :aria-checked="state.colorTheme.value === option.value"
                role="radio"
                @click="applyColorTheme(option.value)"
              >
                <span class="color-theme-swatch" :style="paletteStyle(option.value)" />
                <span>{{ option.label }}</span>
              </button>
            </div>
            <n-color-picker
              v-if="state.colorTheme.value === 'custom'"
              :value="state.customColor.value"
              :show-alpha="false"
              :modes="['hex']"
              size="small"
              @update:value="applyCustomColor"
            />
          </div>
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
.color-theme-picker {
  display: grid;
  gap: 8px;
}

.color-theme-label {
  font-size: 12px;
}

.color-theme-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}

.color-theme-option {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding: 5px 3px 4px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text-secondary);
  background: transparent;
  font: inherit;
  font-size: 10px;
  line-height: 1.2;
  cursor: pointer;
}

.color-theme-option:hover {
  border-color: var(--color-primary);
  color: var(--color-text-primary);
}

.color-theme-option.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-focus-ring);
  color: var(--color-text-primary);
}

.color-theme-swatch {
  width: 100%;
  height: 14px;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px var(--color-border-light);
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
