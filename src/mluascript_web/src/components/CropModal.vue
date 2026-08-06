<script setup>
import { ref, watch } from 'vue'
import { getters, actions, state } from '../store'
import { closeModal } from '../modalStore'
import { NButton, NInput, NSpace, NText } from 'naive-ui'

const props = defineProps({
  modalId: {
    type: String,
    required: true,
  },
})

const canvasRef = ref(null)
const overlayRef = ref(null)
const isCropping = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentX = ref(0)
const currentY = ref(0)
const cropName = ref('template.png')

let imageObj = null

function loadImage() {
  if (!getters.imageUrl.value) {
    imageObj = null
    return
  }
  imageObj = new Image()
  imageObj.onload = () => {
    drawCanvas()
  }
  imageObj.src = getters.imageUrl.value
}

watch(() => getters.imageUrl.value, () => {
  loadImage()
}, { immediate: true })

function drawCanvas() {
  if (!canvasRef.value || !imageObj) return
  const ctx = canvasRef.value.getContext('2d')
  canvasRef.value.width = imageObj.width
  canvasRef.value.height = imageObj.height
  ctx.drawImage(imageObj, 0, 0)
}

function handleMouseDown(event) {
  if (!imageObj || !overlayRef.value) return
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
  if (!isCropping.value || !imageObj || !overlayRef.value) return
  const rect = overlayRef.value.getBoundingClientRect()
  const scaleX = imageObj.width / rect.width
  const scaleY = imageObj.height / rect.height

  currentX.value = Math.max(0, Math.min((event.clientX - rect.left) * scaleX, imageObj.width))
  currentY.value = Math.max(0, Math.min((event.clientY - rect.top) * scaleY, imageObj.height))
}

function handleMouseUp() {
  isCropping.value = false
}

function close() {
  isCropping.value = false
  closeModal(props.modalId)
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
    close()
  } catch (error) {
    console.error(error)
    actions.setStatus(`保存失败: ${error.message}`, 'error')
  } finally {
    state.loading.value = false
  }
}

function boxStyle() {
  if (!imageObj) return {}
  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const w = Math.abs(currentX.value - startX.value)
  const h = Math.abs(currentY.value - startY.value)

  return {
    left: `${(x / imageObj.width) * 100}%`,
    top: `${(y / imageObj.height) * 100}%`,
    width: `${(w / imageObj.width) * 100}%`,
    height: `${(h / imageObj.height) * 100}%`,
  }
}
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 16px; min-height: 0; height: 100%;">
    <div class="crop-container">
      <canvas ref="canvasRef" style="display: none;"></canvas>
      <div
        ref="overlayRef"
        class="image-wrapper"
        @mousedown.prevent="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseUp"
      >
        <img :src="getters.imageUrl.value" class="crop-image" draggable="false" />
        <div class="crop-overlay-box" :style="boxStyle()" v-show="Math.abs(currentX - startX) > 0"></div>
      </div>
    </div>
    
    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
      <n-input v-model:value="cropName" placeholder="保存的文件名，如 btn.png" style="flex: 1;" />
      <n-button type="primary" :disabled="state.loading.value" @click="saveCrop">保存到 resource/image</n-button>
      <n-button @click="close">取消</n-button>
    </div>
  </div>
</template>

<style scoped>
.crop-container {
  flex: 1;
  min-height: 280px;
  overflow: auto;
  position: relative;
  border: 1px dashed var(--n-border-color);
  background: var(--n-color-embedded);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  scrollbar-gutter: stable;
}

.image-wrapper {
  position: relative;
  display: inline-block;
  cursor: crosshair;
}

.crop-image {
  max-width: 100%;
  max-height: calc(90vh - 240px);
  display: block;
}

.crop-overlay-box {
  position: absolute;
  border: 2px dashed var(--color-info);
  background: color-mix(in srgb, var(--color-info) 20%, transparent);
  pointer-events: none;
}
</style>
