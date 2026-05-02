<script setup>
import { computed } from 'vue'
import { NCard, NTabs, NTabPane, NAlert, NButton, NList, NListItem, NThing, NInput, NSelect, NEmpty, NPagination } from 'naive-ui'
import { state, actions } from '../store'

const activeTab = computed({
  get: () => state.deviceTab.value,
  set: (val) => state.deviceTab.value = val
})

function paginateDevices(items, page, pageSize) {
  const normalizedPage = Math.max(1, Number(page) || 1)
  const normalizedPageSize = Math.max(1, Number(pageSize) || 1)
  const start = (normalizedPage - 1) * normalizedPageSize
  return items.slice(start, start + normalizedPageSize)
}

const adbPageCount = computed(() => Math.max(1, Math.ceil(state.adbDevices.value.length / state.devicePageSize.value)))
const emulatorPageCount = computed(() => Math.max(1, Math.ceil(state.emulatorDevices.value.length / state.devicePageSize.value)))
const browserPageCount = computed(() => Math.max(1, Math.ceil(state.browserDevices.value.length / state.devicePageSize.value)))
const win32PageCount = computed(() => Math.max(1, Math.ceil(state.win32Windows.value.length / state.devicePageSize.value)))

const pagedAdbDevices = computed(() => paginateDevices(state.adbDevices.value, state.adbDevicePage.value, state.devicePageSize.value))
const pagedEmulatorDevices = computed(() => paginateDevices(state.emulatorDevices.value, state.emulatorDevicePage.value, state.devicePageSize.value))
const pagedBrowserDevices = computed(() => paginateDevices(state.browserDevices.value, state.browserDevicePage.value, state.devicePageSize.value))
const pagedWin32Windows = computed(() => paginateDevices(state.win32Windows.value, state.win32DevicePage.value, state.devicePageSize.value))

</script>

<template>
  <n-card class="device-view" v-show="state.activeView.value === 'device'" :bordered="false" size="small" style="height: 100%; display: flex; flex-direction: column;" content-style="display: flex; flex-direction: column; padding: 0 16px 16px; flex: 1; min-height: 0;">
    <template #header>设备连接</template>
    
    <n-tabs v-model:value="activeTab" type="line" animated class="device-view-tabs">
      <n-tab-pane name="adb" tab="ADB设备">
        <div class="device-tab-content">
          <n-alert type="default" :show-icon="false" style="margin-bottom: 12px; flex-shrink: 0;">
            {{ state.adbDevices.value.length ? `共搜索到 ${state.adbDevices.value.length} 个 ADB 设备` : '尚未搜索 ADB 设备' }}
          </n-alert>
          <div class="device-list-scroll">
            <n-list bordered hoverable clickable style="background: transparent; margin: 0;">
              <n-empty v-if="!state.adbDevices.value.length" description="暂无 ADB 设备" style="margin-top: 24px;" />
              <n-list-item v-for="device in pagedAdbDevices" :key="device.address" @click="actions.handleAction(() => actions.connectAdb(device.address))">
                <n-thing :title="device.name" :description="device.address" />
              </n-list-item>
            </n-list>
          </div>

          <div class="device-pagination-wrap">
            <n-pagination
              v-model:page="state.adbDevicePage.value"
              :page-count="adbPageCount"
              :page-size="state.devicePageSize.value"
              simple
            />
          </div>

          <div style="flex-shrink: 0; display: flex; flex-direction: column; gap: 12px;">
            <n-button type="primary" block :loading="state.loading.value" @click="actions.handleAction(actions.searchAdb)">搜索 ADB 设备</n-button>
            
            <div style="display: flex; gap: 8px;">
              <n-input v-model:value="state.adbAddress.value" placeholder="手动输入 ADB 地址: 127.0.0.1:5555" style="flex: 1; min-width: 0;" />
              <n-button :loading="state.loading.value" @click="actions.handleAction(() => actions.connectAdb())" style="flex-shrink: 0;">连接 ADB</n-button>
            </div>
          </div>
        </div>
      </n-tab-pane>

      <n-tab-pane name="emulator" tab="模拟器设备">
        <div class="device-tab-content">
          <n-alert type="default" :show-icon="false" style="margin-bottom: 12px; flex-shrink: 0;">
            {{ state.emulatorDevices.value.length ? `已配置 ${state.emulatorDevices.value.length} 个模拟器设备` : '暂无已配置模拟器设备' }}
          </n-alert>
          <div class="device-list-scroll">
            <n-list bordered hoverable clickable style="background: transparent; margin: 0;">
              <n-empty v-if="!state.emulatorDevices.value.length" description="暂无模拟器设备" style="margin-top: 24px;" />
              <n-list-item v-for="device in pagedEmulatorDevices" :key="`emu-${device.address}`" @click="actions.handleAction(() => actions.connectEmulator(device.address))">
                <n-thing :title="device.name" :description="device.address" />
              </n-list-item>
            </n-list>
          </div>

          <div class="device-pagination-wrap">
            <n-pagination
              v-model:page="state.emulatorDevicePage.value"
              :page-count="emulatorPageCount"
              :page-size="state.devicePageSize.value"
              simple
            />
          </div>

          <n-button type="primary" block :loading="state.loading.value" @click="actions.handleAction(actions.loadEmulators)" style="flex-shrink: 0;">加载模拟器配置</n-button>
        </div>
      </n-tab-pane>

      <n-tab-pane name="browser" tab="浏览器设备">
        <div class="device-tab-content">
          <n-alert type="default" :show-icon="false" style="margin-bottom: 12px; flex-shrink: 0;">
            {{ state.browserDevices.value.length ? `已配置 ${state.browserDevices.value.length} 个浏览器设备` : '暂无已配置浏览器设备' }}
          </n-alert>
          <div class="device-list-scroll">
            <n-list bordered hoverable clickable style="background: transparent; margin: 0;">
              <n-empty v-if="!state.browserDevices.value.length" description="暂无浏览器设备" style="margin-top: 24px;" />
              <n-list-item v-for="device in pagedBrowserDevices" :key="device.id" @click="actions.handleAction(() => actions.connectBrowser(device.id))">
                <n-thing :title="device.name" :description="device.address" />
              </n-list-item>
            </n-list>
          </div>

          <div class="device-pagination-wrap">
            <n-pagination
              v-model:page="state.browserDevicePage.value"
              :page-count="browserPageCount"
              :page-size="state.devicePageSize.value"
              simple
            />
          </div>

          <n-button type="primary" block :loading="state.loading.value" @click="actions.handleAction(actions.loadBrowsers)" style="flex-shrink: 0;">加载浏览器配置</n-button>
        </div>
      </n-tab-pane>

      <n-tab-pane name="win32" tab="Win32窗口">
        <div class="device-tab-content">
          <n-alert type="default" :show-icon="false" style="margin-bottom: 12px; flex-shrink: 0;">
            {{ state.win32Windows.value.length ? `共搜索到 ${state.win32Windows.value.length} 个 Win32 窗口` : '尚未搜索 Win32 窗口' }}
          </n-alert>
          <div class="device-list-scroll">
            <n-list bordered hoverable clickable style="background: transparent; margin: 0;">
              <n-empty v-if="!state.win32Windows.value.length" description="暂无 Win32 窗口" style="margin-top: 24px;" />
              <n-list-item v-for="win in pagedWin32Windows" :key="win.hwnd" @click="actions.handleAction(() => actions.connectWin32(win.hwnd))">
                <n-thing :title="win.window_name || '未命名窗口'" :description="String(win.hwnd)" />
              </n-list-item>
            </n-list>
          </div>

          <div class="device-pagination-wrap">
            <n-pagination
              v-model:page="state.win32DevicePage.value"
              :page-count="win32PageCount"
              :page-size="state.devicePageSize.value"
              simple
            />
          </div>

          <n-button type="primary" block :loading="state.loading.value" @click="actions.handleAction(actions.searchWin32)" style="flex-shrink: 0;">搜索 Win32 窗口</n-button>
        </div>
      </n-tab-pane>

    </n-tabs>
  </n-card>
</template>

<style scoped>
.device-view-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.device-view-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
}

.device-view-tabs :deep(.n-tab-pane) {
  height: 100%;
  padding: 12px 0 0 0;
  display: flex;
  flex-direction: column;
}

.device-tab-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.device-list-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: 12px;
  padding-right: 4px;
}

.device-pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
  flex-shrink: 0;
}
</style>
