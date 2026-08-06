<script setup>
import { computed, ref, watch } from 'vue'
import { state, getters, actions } from '../store'
import { NModal, NCard, NSpace, NButton, NText, NTag, NInput, NTabs, NTabPane, NEmpty } from 'naive-ui'

const mode = ref('pick') // 'pick' or 'crop'

// Pick Point State
const screenshotImageRef = ref(null)
const pickedPoint = ref(null)
const copyFeedback = ref('')

// Crop State
const overlayRef = ref(null)
const isCropping = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentX = ref(0)
const currentY = ref(0)
const cropName = ref('template.png')
let imageObj = null

const normalizedPoint = computed(() => {
  if (!pickedPoint.value) return null
  const { imageWidth, imageHeight, x, y } = pickedPoint.value
  if (!imageWidth || !imageHeight) return null
  const scale = 720 / imageHeight
  return {
    rawX: x,
    rawY: y,
    x: Math.round(x * scale),
    y: Math.round(y * scale),
    width: imageWidth,
    height: imageHeight,
    scale,
  }
})

watch(() => getters.imageUrl.value, (val) => {
  if (!val) {
    imageObj = null
    return
  }
  imageObj = new Image()
  imageObj.src = val
  // reset state
  pickedPoint.value = null
  isCropping.value = false
  startX.value = 0
  startY.value = 0
  currentX.value = 0
  currentY.value = 0
}, { immediate: true })

function handleImageClick(event) {
  if (mode.value !== 'pick') return
  
  const wrapper = screenshotImageRef.value
  const img = wrapper?.querySelector('img')
  if (!wrapper || !img) return
  
  const rect = wrapper.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  
  const naturalWidth = img.naturalWidth || rect.width
  const naturalHeight = img.naturalHeight || rect.height
  const scaleX = naturalWidth / rect.width
  const scaleY = naturalHeight / rect.height
  
  const rawX = Math.max(0, Math.min((event.clientX - rect.left) * scaleX, naturalWidth))
  const rawY = Math.max(0, Math.min((event.clientY - rect.top) * scaleY, naturalHeight))
  
  pickedPoint.value = {
    x: Math.round(rawX),
    y: Math.round(rawY),
    imageWidth: naturalWidth,
    imageHeight: naturalHeight,
    displayLeft: event.clientX - rect.left,
    displayTop: event.clientY - rect.top,
    displayWidth: rect.width,
    displayHeight: rect.height,
  }
}

async function copyPointValue(kind) {
  const point = normalizedPoint.value
  if (!point) return
  const text = kind === 'x' ? String(point.x) : kind === 'y' ? String(point.y) : `${point.x}, ${point.y}`
  await navigator.clipboard.writeText(text)
  copyFeedback.value = kind === 'x' ? '已复制 X' : kind === 'y' ? '已复制 Y' : '已复制坐标'
  window.setTimeout(() => {
    if (copyFeedback.value) copyFeedback.value = ''
  }, 1200)
}

function handleMouseDown(event) {
  if (mode.value !== 'crop' || !imageObj || !overlayRef.value) return
  isCropping.value = true
  const rect = overlayRef.value.getBoundingClientRect()
  const scaleX = imageObj.width / rect.width
  const scaleY = imageObj.height / rect.height

  startX.value = (event.clientX - rect.left) * scaleX
  startY.value = (event.clientY - rect.top) * scaleY
  currentX.value = startX.value
  currentY.value = startY.value
}

function handleMouseMove(event) {
  if (!isCropping.value || mode.value !== 'crop' || !imageObj || !overlayRef.value) return
  const rect = overlayRef.value.getBoundingClientRect()
  const scaleX = imageObj.width / rect.width
  const scaleY = imageObj.height / rect.height

  currentX.value = Math.max(0, Math.min((event.clientX - rect.left) * scaleX, imageObj.width))
  currentY.value = Math.max(0, Math.min((event.clientY - rect.top) * scaleY, imageObj.height))
}

function handleMouseUp() {
  if (mode.value !== 'crop') return
  isCropping.value = false
}

async function saveCrop() {
  if (!imageObj) return

  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const w = Math.abs(currentX.value - startX.value)
  const h = Math.abs(currentY.value - startY.value)

  if (w === 0 || h === 0) {
    actions.setStatus('请拖拽选择裁切区域', 'warning')
    return
  }

  const cropCanvas = document.createElement('canvas')
  cropCanvas.width = w
  cropCanvas.height = h
  const ctx = cropCanvas.getContext('2d')
  ctx.drawImage(imageObj, x, y, w, h, 0, 0, w, h)

  const dataUrl = cropCanvas.toDataURL('image/png')
  const base64 = dataUrl.split(',')[1]

  state.loading.value = true
  try {
    const data = await actions.saveCroppedImage(cropName.value, base64)
    actions.setStatus(`已保存裁切图片: ${data.path}`, 'success')
    state.showScreenshot.value = false
  } catch (error) {
    console.error(error)
    actions.setStatus(`保存失败: ${error.message}`, 'error')
  } finally {
    state.loading.value = false
  }
}

function boxStyle() {
  if (!imageObj || mode.value !== 'crop') return { display: 'none' }
  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const w = Math.abs(currentX.value - startX.value)
  const h = Math.abs(currentY.value - startY.value)

  if (w === 0 || h === 0) return { display: 'none' }

  return {
    left: `${(x / imageObj.width) * 100}%`,
    top: `${(y / imageObj.height) * 100}%`,
    width: `${(w / imageObj.width) * 100}%`,
    height: `${(h / imageObj.height) * 100}%`,
  }
}

function close() {
  state.showScreenshot.value = false
}
</script>

<template>
  <n-modal
    v-model:show="state.showScreenshot.value"
    style="width: 100vw; height: 100vh; max-width: 100vw; margin: 0; display: flex; flex-direction: column;"
  >
    <n-card
      title="截图工具"
      :bordered="false"
      size="small"
      role="dialog"
      aria-modal="true"
      closable
      @close="close"
      style="flex: 1; border-radius: 0; display: flex; flex-direction: column; min-height: 0;"
      content-style="display: flex; flex-direction: column; gap: 16px; flex: 1; min-height: 0;"
    >
      <n-tabs v-model:value="mode" type="segment" animated>
        <n-tab-pane name="pick" tab="坐标取点">
          <div style="display: flex; gap: 16px; align-items: center; min-height: 34px;">
            <div style="flex: 1; display: flex; justify-content: space-between; align-items: center;">
              <n-text depth="3">点击下方截图任意位置以获取坐标 (基于 720p 缩放换算)</n-text>
              <n-space align="center" v-if="normalizedPoint">
                <n-tag type="primary">{{ normalizedPoint.x }}, {{ normalizedPoint.y }}</n-tag>
                <n-button size="small" @click="copyPointValue('xy')">复制坐标</n-button>
                <n-button size="small" @click="copyPointValue('x')">复制 X</n-button>
                <n-button size="small" @click="copyPointValue('y')">复制 Y</n-button>
                <n-text type="success" v-if="copyFeedback" style="font-size: 12px; width: 60px;">{{ copyFeedback }}</n-text>
              </n-space>
            </div>
          </div>
        </n-tab-pane>
        <n-tab-pane name="crop" tab="图片裁切">
          <div style="display: flex; gap: 16px; align-items: center; min-height: 34px;">
            <n-text depth="3" style="flex: 1;">拖拽框选裁切区域，然后保存</n-text>
            <n-input v-model:value="cropName" placeholder="保存文件名 (如 btn.png)" style="width: 240px;" />
            <n-button type="primary" @click="saveCrop" :loading="state.loading.value">保存至 Resource</n-button>
          </div>
        </n-tab-pane>
      </n-tabs>

      <div class="screenshot-workspace">
        <div v-if="getters.imageUrl.value" class="screenshot-stage">
          <div
            class="screenshot-image-wrapper"
            ref="screenshotImageRef"
            @click="handleImageClick"
            :style="{ cursor: mode === 'pick' ? 'crosshair' : 'default' }"
          >
            <div
              ref="overlayRef"
              class="crop-overlay"
              @mousedown.prevent="handleMouseDown"
              @mousemove="handleMouseMove"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseUp"
              :style="{ cursor: mode === 'crop' ? 'crosshair' : 'inherit' }"
            >
              <img :src="getters.imageUrl.value" alt="screencap" class="screenshot-img" draggable="false" />
              <div class="crop-box" :style="boxStyle()"></div>
              <div
                v-if="mode === 'pick' && pickedPoint"
                class="pick-marker"
                :style="{
                  left: `${(pickedPoint.displayLeft / pickedPoint.displayWidth) * 100}%`,
                  top: `${(pickedPoint.displayTop / pickedPoint.displayHeight) * 100}%`,
                }"
              ></div>
            </div>
          </div>
        </div>
        <n-empty v-else description="暂无截图数据" style="margin: 60px 0;" />
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
.screenshot-workspace {
  background: var(--n-color-embedded);
  border-radius: 6px;
  border: 1px solid var(--n-border-color);
  padding: 16px;
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.screenshot-stage {
  position: relative;
  display: inline-block;
}

.screenshot-image-wrapper {
  position: relative;
  display: inline-block;
  line-height: 0;
}

.crop-overlay {
  position: relative;
  display: inline-block;
}

.screenshot-img {
  max-width: 100%;
  object-fit: contain;
  display: block;
}

.crop-box {
  position: absolute;
  border: 2px dashed var(--color-info);
  background: color-mix(in srgb, var(--color-info) 20%, transparent);
  pointer-events: none;
}

.pick-marker {
  position: absolute;
  width: 32px;
  height: 32px;
  border: 2px solid var(--n-error-color);
  background: color-mix(in srgb, var(--color-danger) 20%, transparent);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  box-shadow: 0 0 0 2px var(--color-surface), 0 0 10px var(--color-shadow);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.pick-marker::before, .pick-marker::after {
  content: "";
  position: absolute;
  background: var(--n-error-color);
  box-shadow: 0 0 4px var(--color-surface);
}

.pick-marker::before {
  width: 100%;
  height: 2px;
}

.pick-marker::after {
  width: 2px;
  height: 100%;
}
</style>
