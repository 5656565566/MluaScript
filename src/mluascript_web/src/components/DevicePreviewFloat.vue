<script setup>
import { computed, ref } from 'vue'
import { state, actions } from '../store'
import { NButton, NText, NImage, NTag } from 'naive-ui'

const windows = computed(() => state.devicePreviewWindows.value)

const dragState = ref({
  windowId: '',
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
})

function cardStyle(win, index) {
  const x = Number(win.x ?? 24 + index * 32)
  const y = Number(win.y ?? 96 + index * 24)
  return {
    left: `${x}px`,
    top: `${y}px`,
    zIndex: String(1000 + index),
  }
}

function startDrag(event, win) {
  dragState.value = {
    windowId: win.id,
    startX: event.clientX,
    startY: event.clientY,
    originX: Number(win.x || 0),
    originY: Number(win.y || 0),
  }
  window.addEventListener('mousemove', handleDrag)
  window.addEventListener('mouseup', stopDrag)
}

function handleDrag(event) {
  const current = dragState.value
  if (!current.windowId) return
  const nextX = current.originX + (event.clientX - current.startX)
  const nextY = current.originY + (event.clientY - current.startY)
  actions.updateDevicePreviewWindowPosition(current.windowId, nextX, nextY)
}

function stopDrag() {
  dragState.value = {
    windowId: '',
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  }
  window.removeEventListener('mousemove', handleDrag)
  window.removeEventListener('mouseup', stopDrag)
}
</script>

<template>
  <div class="device-preview-layer">
    <div
      v-for="(win, index) in windows"
      :key="win.id"
      class="device-preview-window"
      :style="cardStyle(win, index)"
    >
      <div class="device-preview-header" @mousedown.prevent="startDrag($event, win)">
        <div class="device-preview-title-wrap">
          <span class="device-preview-drag-handle">⋮⋮</span>
          <span class="device-preview-title">{{ win.label || win.id }}</span>
          <n-tag size="small" :bordered="false" type="info">{{ win.intervalMs }} ms</n-tag>
        </div>
        <div class="device-preview-actions">
          <n-button size="tiny" quaternary @click="actions.startDevicePreviewLoop(win.id)">刷新</n-button>
          <n-button size="tiny" quaternary @click="actions.closeDevicePreviewWindow(win.id)">关闭</n-button>
        </div>
      </div>

      <div class="device-preview-body">
        <n-image
          v-if="win.imageBase64"
          :src="`data:image/png;base64,${win.imageBase64}`"
          alt="device-preview"
          object-fit="contain"
          class="device-preview-image"
          preview-disabled
        />
        <div v-else class="device-preview-empty">
          <n-text depth="3">暂无截图预览</n-text>
        </div>
      </div>

      <div class="device-preview-footer">
        <n-text depth="3">设备：{{ win.label || '未命名设备' }}</n-text>
      </div>
    </div>
  </div>
</template>

<style scoped>
.device-preview-layer {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1000;
}

.device-preview-window {
  position: fixed;
  width: 360px;
  max-width: calc(100vw - 24px);
  background: color-mix(in srgb, var(--n-color) 92%, var(--color-background) 8%);
  border: 1px solid color-mix(in srgb, var(--n-border-color) 70%, var(--n-primary-color) 30%);
  border-radius: 14px;
  box-shadow: 0 14px 36px var(--color-shadow);
  overflow: hidden;
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.device-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--n-border-color);
  background: linear-gradient(135deg, color-mix(in srgb, var(--n-primary-color) 16%, var(--n-color-embedded) 84%), var(--n-color-embedded));
  cursor: move;
  user-select: none;
}

.device-preview-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.device-preview-drag-handle {
  color: var(--n-text-color-disabled);
  letter-spacing: -1px;
  font-size: 14px;
}

.device-preview-title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-preview-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.device-preview-body {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(45deg, color-mix(in srgb, var(--color-text-primary) 3%, transparent) 25%, transparent 25%, transparent 75%, color-mix(in srgb, var(--color-text-primary) 3%, transparent) 75%),
    linear-gradient(45deg, color-mix(in srgb, var(--color-text-primary) 3%, transparent) 25%, transparent 25%, transparent 75%, color-mix(in srgb, var(--color-text-primary) 3%, transparent) 75%),
    color-mix(in srgb, var(--n-color-embedded) 90%, black 10%);
  background-size: 24px 24px;
  background-position: 0 0, 12px 12px;
  overflow: hidden;
}

.device-preview-image {
  width: 100%;
  height: 100%;
}

.device-preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.device-preview-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--n-border-color);
  background: color-mix(in srgb, var(--n-color) 92%, var(--n-color-embedded) 8%);
}
</style>
