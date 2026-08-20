<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { state, getters, actions } from '../store'
import { NModal, NCard, NSpace, NButton, NDropdown, NEmpty, NForm, NFormItem, NIcon, NInput, NSlider, NTabPane, NTabs, NTag, NText, NTooltip } from 'naive-ui'
import { ChevronForwardOutline, FolderOutline, HomeOutline } from '@vicons/ionicons5'
import VisionDialogHeader from './VisionDialogHeader.vue'

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
const saveVisible = ref(false)
const saveDomain = ref('')
const saveDirectory = ref('')
let imageObj = null

const resourceDomainOptions = computed(() => Object.entries(state.currentManifest.value?.resources || {})
  .map(([key, root]) => ({
    label: `${key} (${String(root || '').replaceAll('\\', '/')})`,
    value: key,
  }))
  .filter(option => option.value))

const selectedResourceRoot = computed(() => String(
  state.currentManifest.value?.resources?.[saveDomain.value] || '',
).replaceAll('\\', '/').replace(/^\/+|\/+$/g, ''))

const saveDirectoryNodes = computed(() => {
  if (!saveDomain.value) {
    return resourceDomainOptions.value.map(option => ({
      key: `domain:${option.value}`,
      label: option.value,
      description: selectedRootForDomain(option.value),
      domain: option.value,
      directory: '',
    }))
  }

  const root = selectedResourceRoot.value
  const current = saveDirectory.value
  const directories = new Map()
  if (!root) return []
  for (const item of state.projectTree.value || []) {
    const path = String(item?.path || '').replaceAll('\\', '/').replace(/^\/+|\/+$/g, '')
    if (path !== root && !path.startsWith(`${root}/`)) continue
    const relative = path === root ? '' : path.slice(root.length + 1)
    const directory = item?.kind === 'directory' ? relative : relative.split('/').slice(0, -1).join('/')
    if (!directory || (current && directory !== current && !directory.startsWith(`${current}/`))) continue
    const remaining = current ? directory.slice(current.length).replace(/^\/+/, '') : directory
    const nextSegment = remaining.split('/').filter(Boolean)[0]
    if (!nextSegment) continue
    const nextDirectory = [current, nextSegment].filter(Boolean).join('/')
    directories.set(nextDirectory, nextSegment)
  }
  return [...directories.entries()]
    .sort((left, right) => left[1].localeCompare(right[1], 'zh-Hans-CN'))
    .map(([directory, label]) => ({
      key: `directory:${directory}`,
      label,
      description: `${root}/${directory}`,
      domain: saveDomain.value,
      directory,
    }))
})

function selectedRootForDomain(domain) {
  return String(state.currentManifest.value?.resources?.[domain] || '')
    .replaceAll('\\', '/')
    .replace(/^\/+|\/+$/g, '')
}

const saveBreadcrumbs = computed(() => {
  if (!saveDomain.value) return []
  return [saveDomain.value, ...saveDirectory.value.split('/').filter(Boolean)]
})

const foregroundEditorKind = computed(() => {
  if (state.blocklyEditor.value) return 'blockly'
  if (state.textCodeEditor.value) return 'lua'
  return ''
})

const hasCropSelection = computed(() => (
  Math.abs(currentX.value - startX.value) > 0 && Math.abs(currentY.value - startY.value) > 0
))

const cropSelectionLabel = computed(() => {
  if (!hasCropSelection.value) return ''
  return `${Math.round(Math.abs(currentX.value - startX.value))} × ${Math.round(Math.abs(currentY.value - startY.value))}`
})

const saveTargetPathPreview = computed(() => {
  if (!selectedResourceRoot.value) return '请选择资源目录'
  return [selectedResourceRoot.value, saveDirectory.value, cropName.value].filter(Boolean).join('/')
})

const clipboardOptions = computed(() => {
  if (mode.value === 'pick') {
    return [
      { label: '复制坐标', key: 'copy-point', disabled: !normalizedPoint.value },
      { label: '复制点击 Lua', key: 'copy-point-lua', disabled: !normalizedPoint.value },
    ]
  }
  if (mode.value === 'crop') {
    return [{ label: '复制 ROI Lua', key: 'copy-roi-lua', disabled: !hasCropSelection.value }]
  }
  return [
    { label: '复制 HEX', key: 'copy-color-hex', disabled: !pickedColor.value },
    { label: '复制 RGB', key: 'copy-color-rgb', disabled: !pickedColor.value },
  ]
})

const insertOptions = computed(() => {
  if (!foregroundEditorKind.value) return []
  const target = foregroundEditorKind.value === 'blockly' ? 'Blockly' : 'Lua'
  if (mode.value === 'color') {
    return [{
      label: `插入颜色 ${target}`,
      key: `insert-color-${foregroundEditorKind.value}`,
      disabled: !pickedColor.value,
    }]
  }
  const isPoint = mode.value === 'pick'
  return [{
    label: `插入${isPoint ? '点击' : ' ROI'} ${target}`,
    key: `insert-${isPoint ? 'point' : 'roi'}-${foregroundEditorKind.value}`,
    disabled: isPoint ? !normalizedPoint.value : !hasCropSelection.value,
  }]
})

const normalizedPoint = computed(() => {
  if (!pickedPoint.value) return null
  const { imageWidth, imageHeight, x, y } = pickedPoint.value
  if (!imageWidth || !imageHeight) return null
  const maaPoint = state.visionSession.value?.point
  return {
    rawX: x,
    rawY: y,
    x: maaPoint?.x ?? Math.round(x),
    y: maaPoint?.y ?? Math.round(y),
    width: imageWidth,
    height: imageHeight,
    scale: 1,
  }
})

watch(() => getters.imageUrl.value, (val) => {
  imageReady.value = false
  if (!val) {
    imageObj = null
    return
  }
   imageObj = new Image()
   imageObj.onload = () => {
     imageReady.value = true
    actions.setVisionSource?.({
      width: imageObj.naturalWidth || imageObj.width || 0,
      height: imageObj.naturalHeight || imageObj.height || 0,
    })
    state.imageRecognitionDraft.value = {
      ...state.imageRecognitionDraft.value,
      imageWidth: imageObj.naturalWidth || imageObj.width || 0,
      imageHeight: imageObj.naturalHeight || imageObj.height || 0,
    }
   }
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
  actions.setVisionPoint?.({ x: rawX, y: rawY, imageWidth: naturalWidth, imageHeight: naturalHeight })
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
    const imageBase64 = dataUrl.split(',', 2)[1] || ''
    const imageMimeType = file.type || 'image/png'
    state.screenshotBase64.value = imageBase64
    if (state.screenshotMimeType) state.screenshotMimeType.value = imageMimeType
    if (state.screenshotImagePath) state.screenshotImagePath.value = ''
    state.screenshotPath.value = file.name
    actions.setVisionSource?.({ type: 'upload', path: '', base64: imageBase64, mimeType: imageMimeType })
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

async function handleClipboardSelect(key) {
  if (key === 'copy-point') return copyPointValue('xy')
  if (key === 'copy-point-lua') return runVisionAction(() => actions.copyVisionLua({ mode: 'point' }))
  if (key === 'copy-roi-lua') return runVisionAction(() => actions.copyVisionLua({ mode: 'roi' }))
  if (key === 'copy-color-hex') return copyColor('hex')
  if (key === 'copy-color-rgb') return copyColor('rgb')
}

function handleInsertSelect(key) {
  const recipeMode = key.includes('-point-') ? 'point' : key.includes('-color-') ? 'color' : 'roi'
  const options = recipeMode === 'color' ? { mode: recipeMode, color: pickedColor.value?.hex } : { mode: recipeMode }
  if (key.endsWith('-blockly')) {
    return runVisionAction(() => actions.insertVisionIntoBlockly(options))
  }
  return runVisionAction(() => actions.insertVisionIntoLua(options))
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
  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const width = Math.abs(currentX.value - startX.value)
  const height = Math.abs(currentY.value - startY.value)
  if (width > 0 && height > 0)   actions.setVisionRoi?.({ rawX: x, rawY: y, rawWidth: width, rawHeight: height, imageWidth: imageObj.width, imageHeight: imageObj.height })
}

async function runVisionAction(action) {
  try {
    await action()
  } catch (error) {
    actions.setStatus(error?.message || '当前编辑器不可用', 'error')
  }
}

function openSaveCropDialog() {
  if (!hasCropSelection.value) {
    actions.setStatus('请拖拽选择裁切区域', 'warning')
    return
  }
  if (!resourceDomainOptions.value.length) {
    actions.setStatus('当前项目没有声明资源域', 'warning')
    return
  }
  if (!resourceDomainOptions.value.some(option => option.value === saveDomain.value)) {
    saveDomain.value = ''
    saveDirectory.value = ''
  }
  saveVisible.value = true
}

function updateSaveDomain(value) {
  saveDomain.value = value || ''
  saveDirectory.value = ''
}

function openSaveDirectory(node) {
  if (node.domain && node.directory === '') {
    updateSaveDomain(node.domain)
    return
  }
  saveDirectory.value = node.directory
}

function navigateSaveDirectory(index) {
  if (index < 0) {
    saveDomain.value = ''
    saveDirectory.value = ''
    return
  }
  if (index === 0) {
    saveDirectory.value = ''
    return
  }
  saveDirectory.value = saveBreadcrumbs.value.slice(1, index + 1).join('/')
}

async function saveCrop() {
  if (!imageObj) return
  if (!selectedResourceRoot.value) {
    actions.setStatus('请先选择资源目录', 'warning')
    return
  }

  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const w = Math.abs(currentX.value - startX.value)
  const h = Math.abs(currentY.value - startY.value)

  if (w === 0 || h === 0) {
    actions.setStatus('请拖拽选择裁切区域', 'warning')
    return
  }
  actions.setVisionRoi?.({ rawX: x, rawY: y, rawWidth: w, rawHeight: h, imageWidth: imageObj.width, imageHeight: imageObj.height })

  const cropCanvas = document.createElement('canvas')
  cropCanvas.width = w
  cropCanvas.height = h
  const ctx = cropCanvas.getContext('2d')
  ctx.drawImage(imageObj, x, y, w, h, 0, 0, w, h)

  const dataUrl = cropCanvas.toDataURL('image/png')
  const base64 = dataUrl.split(',')[1]

  state.loading.value = true
  try {
    const targetDirectory = [selectedResourceRoot.value, saveDirectory.value].filter(Boolean).join('/')
    const data = await actions.saveCroppedImage(cropName.value, base64, targetDirectory)
    actions.setStatus(`已保存裁切图片: ${data.path}`, 'success')
    saveVisible.value = false
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

function switchVisionDialog(key) {
  if (key === 'recognition') actions.openImageRecognitionDebugModal()
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
      :bordered="false"
      size="small"
      role="dialog"
      aria-modal="true"
      closable
      @close="close"
      style="flex: 1; border-radius: 0; display: flex; flex-direction: column; min-height: 0;"
      content-style="display: flex; flex-direction: column; gap: 16px; flex: 1; min-height: 0;"
    >
      <template #header>
        <VisionDialogHeader label="截图预览" :on-select="switchVisionDialog" />
      </template>
      <div class="screenshot-toolbar">
        <n-space align="center" :wrap="true" class="screenshot-toolbar-main">
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
        <n-space align="center" :wrap="false" class="screenshot-toolbar-actions">
          <n-space v-if="mode === 'pick' && normalizedPoint" align="center" :size="6">
            <n-tag type="primary">Maa {{ normalizedPoint.x }}, {{ normalizedPoint.y }}</n-tag>
            <n-text depth="3" class="screenshot-coordinate-text">原图 {{ normalizedPoint.rawX }}, {{ normalizedPoint.rawY }}</n-text>
          </n-space>
          <n-space v-else-if="mode === 'color' && pickedColor" align="center" :size="6">
            <span class="color-swatch" :style="{ backgroundColor: pickedColor.hex }"></span>
            <n-tag>{{ pickedColor.hex }}</n-tag>
            <n-tag>{{ pickedColor.rgb }}</n-tag>
          </n-space>
          <n-tag v-else-if="mode === 'crop' && cropSelectionLabel" type="info">裁切 {{ cropSelectionLabel }}</n-tag>
          <n-text v-if="copyFeedback" type="success" class="screenshot-copy-feedback">{{ copyFeedback }}</n-text>
          <n-dropdown trigger="click" :options="clipboardOptions" @select="handleClipboardSelect">
            <n-button size="small">复制</n-button>
          </n-dropdown>
          <n-dropdown trigger="click" :options="insertOptions" @select="handleInsertSelect">
            <n-button size="small" :disabled="!insertOptions.length">插入</n-button>
          </n-dropdown>
          <n-button
            size="small"
            type="primary"
            :disabled="mode !== 'crop' || !hasCropSelection"
            @click="openSaveCropDialog"
          >保存</n-button>
        </n-space>
      </div>
      <n-tabs v-model:value="mode" type="segment" animated class="screenshot-tabs">
        <n-tab-pane name="pick">
          <template #tab>
            <n-tooltip trigger="hover">
              <template #trigger><span>坐标取点</span></template>
              点击图片获取坐标
            </n-tooltip>
          </template>
        </n-tab-pane>
        <n-tab-pane name="crop">
          <template #tab>
            <n-tooltip trigger="hover">
              <template #trigger><span>图片裁切</span></template>
              拖拽框选裁切区域，然后保存
            </n-tooltip>
          </template>
        </n-tab-pane>
        <n-tab-pane name="color">
          <template #tab>
            <n-tooltip trigger="hover">
              <template #trigger><span>颜色拾取</span></template>
              点击图片获取像素颜色
            </n-tooltip>
          </template>
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

  <n-modal v-model:show="saveVisible" preset="card" title="保存裁切图片" style="width: min(520px, calc(100vw - 32px));">
    <n-form label-placement="top">
       <n-form-item label="保存位置">
         <div class="save-directory-browser">
           <div class="save-directory-breadcrumb">
             <n-button quaternary size="small" title="资源根目录" aria-label="资源根目录" @click="navigateSaveDirectory(-1)">
               <template #icon><n-icon><home-outline /></n-icon></template>
               resources
             </n-button>
             <template v-for="(segment, index) in saveBreadcrumbs" :key="`${segment}-${index}`">
               <n-icon depth="3" size="14"><chevron-forward-outline /></n-icon>
               <n-button quaternary size="small" @click="navigateSaveDirectory(index)">{{ segment }}</n-button>
             </template>
           </div>
           <div class="save-directory-list">
             <button
               v-for="node in saveDirectoryNodes"
               :key="node.key"
               type="button"
               class="save-directory-row"
               @click="openSaveDirectory(node)"
             >
               <n-icon size="19"><folder-outline /></n-icon>
               <span class="save-directory-label">
                 <strong>{{ node.label }}</strong>
                 <small>{{ node.description }}</small>
               </span>
               <n-icon depth="3" size="16"><chevron-forward-outline /></n-icon>
             </button>
             <n-empty v-if="!saveDirectoryNodes.length" description="没有可进入的子目录" />
           </div>
         </div>
       </n-form-item>
      <n-form-item label="文件名">
        <n-input v-model:value="cropName" placeholder="例如 template.png" />
      </n-form-item>
       <n-text depth="3">{{ saveTargetPathPreview }}</n-text>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="saveVisible = false">取消</n-button>
         <n-button type="primary" :disabled="!selectedResourceRoot" :loading="state.loading.value" @click="saveCrop">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.screenshot-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex: 0 0 auto;
  padding: 8px 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  background: var(--n-color-embedded);
}

.screenshot-toolbar-main {
  min-width: 0;
}

.screenshot-toolbar-actions {
  flex: 0 0 auto;
  margin-left: auto;
}

.screenshot-tabs {
  flex: 0 0 auto;
}

.screenshot-tabs :deep(.n-tabs-pane-wrapper),
.screenshot-tabs :deep(.n-tab-pane) {
  min-height: 0;
}

.screenshot-tabs :deep(.n-tab-pane) {
  padding-top: 0;
  padding-bottom: 0;
}

.screenshot-upload-input {
  display: none;
}

.save-directory-browser {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
}

.save-directory-breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  min-height: 42px;
  padding: 4px 8px;
  overflow-x: auto;
  border-bottom: 1px solid var(--n-border-color);
  background: var(--n-color-embedded);
  white-space: nowrap;
}

.save-directory-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 96px;
  max-height: 210px;
  padding: 6px;
  overflow-y: auto;
}

.save-directory-row {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 10px;
  padding: 8px 10px;
  border: 0;
  border-radius: 4px;
  color: var(--n-text-color);
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.save-directory-row:hover {
  background: var(--n-hover-color);
}

.save-directory-label {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.save-directory-label strong,
.save-directory-label small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.save-directory-label small {
  color: var(--n-text-color-3);
  font-size: 12px;
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

@media (max-width: 900px) {
  .screenshot-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .screenshot-toolbar-actions {
    margin-left: 0;
  }
}
</style>
