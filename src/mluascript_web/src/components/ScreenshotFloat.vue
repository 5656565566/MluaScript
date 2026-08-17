<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { state, getters, actions } from '../store'
import { NModal, NCard, NSpace, NButton, NText, NTag, NInput, NTabs, NTabPane, NEmpty, NSlider } from 'naive-ui'

const mode = ref('pick') // 'pick' or 'crop'
const zoom = ref(1)
const imageReady = ref(false)
const panX = ref(0)
const panY = ref(0)
const isPanning = ref(false)
const panStartX = ref(0)
const panStartY = ref(0)
const panOriginX = ref(0)
const panOriginY = ref(0)
const MIN_ZOOM = 0.25
const MAX_ZOOM = 4

// Pick Point State
const screenshotImageRef = ref(null)
const pickedPoint = ref(null)
const copyFeedback = ref('')
const pickedColor = ref(null)
const uploadInputRef = ref(null)

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
  imageReady.value = false
  if (!val) {
    imageObj = null
    return
  }
  imageObj = new Image()
  imageObj.onload = () => { imageReady.value = true }
  imageObj.src = val
  zoom.value = 1
  panX.value = 0
  panY.value = 0
  pickedColor.value = null
  // reset state
  pickedPoint.value = null
  isCropping.value = false
  startX.value = 0
  startY.value = 0
  currentX.value = 0
  currentY.value = 0
}, { immediate: true })

function setZoom(value) {
  const numericValue = Number(value)
  const nextZoom = Number.isFinite(numericValue) ? numericValue : 1
  zoom.value = Math.round(Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, nextZoom)) * 100) / 100
}

function formatZoom(value = zoom.value) {
  return Number(value).toFixed(2)
}

function zoomIn() {
  setZoom(zoom.value + 0.25)
}

function zoomOut() {
  setZoom(zoom.value - 0.25)
}

function resetZoom() {
  setZoom(1)
}

function handleWheel(event) {
  if (!getters.imageUrl.value) return
  event.preventDefault()
  setZoom(zoom.value + (event.deltaY < 0 ? 0.1 : -0.1))
}

function handleContextMenu(event) {
  event.preventDefault()
}

function handlePanStart(event) {
  if (event.button !== 2 || !getters.imageUrl.value) return
  event.preventDefault()
  isPanning.value = true
  panStartX.value = event.clientX
  panStartY.value = event.clientY
  panOriginX.value = panX.value
  panOriginY.value = panY.value
  window.addEventListener('mousemove', handlePanMove)
  window.addEventListener('mouseup', handlePanEnd)
}

function handlePanMove(event) {
  if (!isPanning.value) return
  panX.value = panOriginX.value + event.clientX - panStartX.value
  panY.value = panOriginY.value + event.clientY - panStartY.value
}

function handlePanEnd() {
  if (!isPanning.value) return
  isPanning.value = false
  window.removeEventListener('mousemove', handlePanMove)
  window.removeEventListener('mouseup', handlePanEnd)
}

function handleImageClick(event) {
  if (!['pick', 'color'].includes(mode.value)) return
  
  const wrapper = overlayRef.value
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

  if (mode.value === 'color') {
    const canvas = document.createElement('canvas')
    canvas.width = 1
    canvas.height = 1
    const context = canvas.getContext('2d', { willReadFrequently: true })
    context.drawImage(imageObj, Math.floor(rawX), Math.floor(rawY), 1, 1, 0, 0, 1, 1)
    const [r, g, b] = context.getImageData(0, 0, 1, 1).data
    pickedColor.value = {
      hex: `#${[r, g, b].map(value => value.toString(16).padStart(2, '0')).join('').toUpperCase()}`,
      rgb: `${r}, ${g}, ${b}`,
    }
    return
  }
  
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

async function copyColor(kind = 'hex') {
  if (!pickedColor.value) return
  await navigator.clipboard.writeText(pickedColor.value[kind])
  actions.setStatus(`已复制颜色 ${pickedColor.value[kind]}`, 'success')
}

function chooseUploadImage() {
  uploadInputRef.value?.click()
}

function handleUploadImage(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    actions.setStatus('请选择图片文件', 'warning')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const dataUrl = String(reader.result || '')
    state.screenshotBase64.value = dataUrl.split(',', 2)[1] || ''
    if (state.screenshotMimeType) state.screenshotMimeType.value = file.type || 'image/png'
    if (state.screenshotImagePath) state.screenshotImagePath.value = ''
    state.screenshotPath.value = file.name
  }
  reader.readAsDataURL(file)
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
  if (event.button !== 0 || mode.value !== 'crop' || !imageObj || !overlayRef.value) return
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

const imageTransformStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  visibility: imageReady.value ? 'visible' : 'hidden',
}))

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
  handlePanEnd()
  state.showScreenshot.value = false
}

onBeforeUnmount(() => {
  handlePanEnd()
})
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
      <div class="screenshot-toolbar">
        <n-space align="center" :wrap="true">
          <input ref="uploadInputRef" type="file" accept="image/*" class="screenshot-upload-input" @change="handleUploadImage" />
          <n-button size="small" @click="chooseUploadImage">上传图片</n-button>
          <n-text depth="3">缩放</n-text>
          <n-button size="small" :disabled="zoom <= MIN_ZOOM" @click="zoomOut">−</n-button>
          <n-slider
            :value="zoom"
            :min="MIN_ZOOM"
            :max="MAX_ZOOM"
            :step="0.05"
            :format-tooltip="formatZoom"
            style="width: 180px;"
            @update:value="setZoom"
          />
          <n-button size="small" :disabled="zoom >= MAX_ZOOM" @click="zoomIn">+</n-button>
          <n-button size="small" secondary @click="resetZoom">{{ formatZoom() }}x</n-button>
          <n-text depth="3" class="screenshot-hint">滚轮缩放，按住鼠标右键拖动图片</n-text>
        </n-space>
      </div>
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
        <n-tab-pane name="color" tab="颜色拾取">
          <div class="screenshot-mode-row">
            <n-text depth="3" style="flex: 1;">点击图片获取像素颜色</n-text>
            <n-space v-if="pickedColor" align="center">
              <span class="color-swatch" :style="{ backgroundColor: pickedColor.hex }"></span>
              <n-tag>{{ pickedColor.hex }}</n-tag>
              <n-tag>{{ pickedColor.rgb }}</n-tag>
              <n-button size="small" @click="copyColor('hex')">复制 HEX</n-button>
              <n-button size="small" @click="copyColor('rgb')">复制 RGB</n-button>
            </n-space>
          </div>
        </n-tab-pane>
      </n-tabs>

      <div
        class="screenshot-workspace"
        :class="{ 'is-panning': isPanning }"
        @wheel="handleWheel"
        @contextmenu="handleContextMenu"
        @mousedown="handlePanStart"
      >
        <div v-if="getters.imageUrl.value" class="screenshot-stage">
          <div
            class="screenshot-image-wrapper"
            ref="screenshotImageRef"
            @click="handleImageClick"
            :style="{ cursor: ['pick', 'color'].includes(mode) ? 'crosshair' : 'default' }"
          >
            <div
              ref="overlayRef"
              class="crop-overlay"
              :style="{ ...imageTransformStyle, cursor: isPanning ? 'grabbing' : mode === 'crop' ? 'crosshair' : 'inherit' }"
              @mousedown.prevent="handleMouseDown"
              @mousemove="handleMouseMove"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseUp"
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
.screenshot-toolbar {
  flex: 0 0 auto;
  padding: 8px 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  background: var(--n-color-embedded);
}

.screenshot-upload-input {
  display: none;
}

.screenshot-mode-row {
  display: flex;
  align-items: center;
  min-height: 34px;
  gap: 12px;
}

.color-swatch {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
}

.screenshot-hint {
  font-size: 12px;
}

.screenshot-workspace.is-panning {
  cursor: grabbing;
  user-select: none;
}

.screenshot-workspace {
  background: var(--n-color-embedded);
  cursor: default;
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
