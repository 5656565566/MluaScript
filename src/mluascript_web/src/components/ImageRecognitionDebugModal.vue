<script setup>
import { computed, ref } from 'vue'
import { NButton, NEmpty, NGrid, NGridItem, NInput, NInputNumber, NSelect, NSpace, NTag, NText } from 'naive-ui'
import { state, getters, actions } from '../store'

const props = defineProps({
  modalId: { type: String, required: true },
})

const imageKinds = [
  { label: 'OCR 文字识别', value: 'ocr' },
  { label: '模板匹配', value: 'template' },
  { label: '特征匹配', value: 'feature' },
  { label: '颜色匹配', value: 'color' },
  { label: '神经网络检测', value: 'nnd' },
]
const draft = state.imageRecognitionDraft
const imageRef = ref(null)
const imageSize = ref({ width: 0, height: 0 })
const isSelecting = ref(false)
const selectionStart = ref({ x: 0, y: 0 })
const resourcePreviewCollapsed = ref(false)
const projectKey = computed(() => state.currentProject?.value?.key || '')
const imageUrl = computed(() => draft.value.imageBase64
  ? `data:${draft.value.imageMimeType || 'image/png'};base64,${draft.value.imageBase64}`
  : '')
const resourceFiles = computed(() => (state.projectTree.value || []).filter(item => item.kind === 'file'))
const imageResources = computed(() => resourceFiles.value.filter(item => /\.(png|jpe?g|gif|webp|bmp|svg|avif|ico)$/i.test(item.path)))
const templateResources = computed(() => resourceFiles.value.filter(item => /\.(png|jpe?g|gif|webp|bmp|svg|avif|ico)$/i.test(item.path)))
const recognitionResourceOptions = computed(() => {
  const options = []
  for (const [resourceKey, rawRoot] of Object.entries(state.currentManifest.value?.resources || {})) {
    const root = String(rawRoot || '').replaceAll('\\', '/').replace(/\/$/, '')
    if (!root) continue
    for (const item of templateResources.value) {
      if (!item.path.startsWith(`${root}/`)) continue
      const relative = item.path.slice(root.length + 1)
      options.push({
        label: `${resourceKey}:${relative}`,
        value: `${resourceKey}:${relative}`,
        projectPath: item.path,
      })
    }
  }
  return options
})
const modelResources = computed(() => resourceFiles.value.filter(item => /\.(onnx|xml|bin|pth|engine)$/i.test(item.path)))
const modelOptions = computed(() => {
  const options = []
  const seen = new Set()
  for (const [modelKey, model] of Object.entries(state.currentManifest.value?.models || {})) {
    if (String(model?.type || '').toLowerCase() !== 'maa.nnd') continue
    const declaredPath = String(model?.path || '').replaceAll('\\', '/').replace(/\/$/, '')
    if (!declaredPath) continue
    const candidates = modelResources.value.filter(item => (
      item.path === declaredPath || item.path.startsWith(`${declaredPath}/`)
    ))
    const resolved = candidates.length ? candidates : [{ path: declaredPath }]
    for (const candidate of resolved) {
      if (seen.has(candidate.path)) continue
      seen.add(candidate.path)
      options.push({
        label: candidates.length > 1 ? `${modelKey}/${candidate.path.split('/').pop()}` : modelKey,
        value: candidate.path,
        description: candidate.path,
      })
    }
  }
  for (const item of modelResources.value) {
    if (seen.has(item.path)) continue
    seen.add(item.path)
    options.push({ label: item.path.split('/').pop(), value: item.path, description: item.path })
  }
  return options
})
const selectedResourceUrl = computed(() => {
  const path = draft.value.imagePath
  const selected = recognitionResourceOptions.value.find(item => item.value === path)
  return projectKey.value && path ? actions.projectFileDownloadUrl(selected?.projectPath || path) : ''
})
const recognitionResourcePreviewUrl = computed(() => {
  if (!['template', 'feature'].includes(draft.value.kind) || !draft.value.templatePath || !projectKey.value) return ''
  const selected = recognitionResourceOptions.value.find(item => item.value === draft.value.templatePath)
  return actions.projectFileDownloadUrl(selected?.projectPath || draft.value.templatePath)
})
const recognitionResourceName = computed(() => String(draft.value.templatePath || '') || '识图资源')
const activeImageUrl = computed(() => imageUrl.value || selectedResourceUrl.value)
const hasTestImage = computed(() => Boolean(activeImageUrl.value))
const hasRoi = computed(() => Number(draft.value.roiWidth) > 0 && Number(draft.value.roiHeight) > 0)
const roiBoxStyle = computed(() => {
  if (!hasRoi.value || !imageSize.value.width || !imageSize.value.height) return { display: 'none' }
  return {
    left: `${(Number(draft.value.roiX) / imageSize.value.width) * 100}%`,
    top: `${(Number(draft.value.roiY) / imageSize.value.height) * 100}%`,
    width: `${(Number(draft.value.roiWidth) / imageSize.value.width) * 100}%`,
    height: `${(Number(draft.value.roiHeight) / imageSize.value.height) * 100}%`,
  }
})

function update(patch) {
  draft.value = { ...draft.value, ...patch, error: '' }
}

async function useNewScreenshot() {
  try {
    const data = await actions.handleAction(() => actions.doScreencap({ showPreview: false }))
    if (data?.imageBase64) update({ imageBase64: data.imageBase64, imageMimeType: 'image/png', imagePath: '', result: null })
    else if (state.screenshotBase64.value) update({ imageBase64: state.screenshotBase64.value, imageMimeType: 'image/png', imagePath: '', result: null })
  } catch (error) {
    update({ error: error?.message || '截图失败' })
  }
}

function useSavedImage(path) {
  update({ imagePath: path || '', imageBase64: '', result: null })
}

function openImageResourcePicker() {
  actions.openBlocklyPicker({
    title: '选择测试图片',
    treeMode: true,
    items: recognitionResourceOptions.value,
    currentValue: draft.value.imagePath || null,
    emptyText: 'resources 中没有可用图片',
    onSelect: useSavedImage,
  })
}

function openTemplateResourcePicker() {
  actions.openBlocklyPicker({
    title: '选择识图模板资源',
    treeMode: true,
    items: recognitionResourceOptions.value,
    currentValue: draft.value.templatePath || null,
    emptyText: 'resources 中没有可用模板图片',
    onSelect: value => update({ templatePath: value || '', result: null }),
  })
}

function useCurrentScreenshot() {
  if (!state.screenshotBase64.value) return
  update({
    imageBase64: state.screenshotBase64.value,
    imageMimeType: state.screenshotMimeType?.value || 'image/png',
    imagePath: '',
    result: null,
  })
}

function clearImage() {
  update({ imageBase64: '', imagePath: '' })
}

function parseRoi() {
  if (!hasRoi.value) return null
  return [draft.value.roiX, draft.value.roiY, draft.value.roiWidth, draft.value.roiHeight]
    .map(value => Math.max(0, Math.round(Number(value) || 0)))
}

function updateRoiField(key, value) {
  update({ [key]: value === null ? null : Math.max(0, Math.round(Number(value) || 0)), result: null })
}

function clearRoi() {
  update({ roiX: null, roiY: null, roiWidth: null, roiHeight: null, result: null })
}

function handleImageLoad(event) {
  imageSize.value = {
    width: event.target.naturalWidth || 0,
    height: event.target.naturalHeight || 0,
  }
}

function imagePoint(event) {
  const image = imageRef.value
  if (!image?.naturalWidth || !image?.naturalHeight) return null
  const rect = image.getBoundingClientRect()
  if (!rect.width || !rect.height) return null
  return {
    x: Math.max(0, Math.min(image.naturalWidth, (event.clientX - rect.left) * image.naturalWidth / rect.width)),
    y: Math.max(0, Math.min(image.naturalHeight, (event.clientY - rect.top) * image.naturalHeight / rect.height)),
  }
}

function startRoiSelection(event) {
  if (event.button !== 0) return
  const point = imagePoint(event)
  if (!point) return
  event.preventDefault()
  event.currentTarget.setPointerCapture?.(event.pointerId)
  isSelecting.value = true
  selectionStart.value = point
  update({
    roiX: Math.round(point.x),
    roiY: Math.round(point.y),
    roiWidth: 0,
    roiHeight: 0,
    result: null,
  })
}

function moveRoiSelection(event) {
  if (!isSelecting.value) return
  const point = imagePoint(event)
  if (!point) return
  const start = selectionStart.value
  update({
    roiX: Math.round(Math.min(start.x, point.x)),
    roiY: Math.round(Math.min(start.y, point.y)),
    roiWidth: Math.round(Math.abs(point.x - start.x)),
    roiHeight: Math.round(Math.abs(point.y - start.y)),
    result: null,
  })
}

function finishRoiSelection(event) {
  if (!isSelecting.value) return
  moveRoiSelection(event)
  isSelecting.value = false
  event.currentTarget.releasePointerCapture?.(event.pointerId)
}

function hexToRgb(value) {
  const text = String(value || '').trim().replace(/^#/, '')
  if (!/^[0-9a-f]{6}$/i.test(text)) return null
  return [0, 2, 4].map(offset => Number.parseInt(text.slice(offset, offset + 2), 16))
}

async function runRecognition() {
  if (!projectKey.value) {
    update({ error: '请先打开项目' })
    return
  }
  if (!draft.value.imageBase64 && !draft.value.imagePath) {
    update({ error: '请先选择测试图片或获取新截图' })
    return
  }
  try {
    const result = await actions.runImageRecognition({
      kind: draft.value.kind,
      imagePath: draft.value.imagePath,
      imageBase64: draft.value.imageBase64,
      templatePath: draft.value.templatePath,
      modelPath: draft.value.modelPath,
      expected: draft.value.expected,
      targets: draft.value.targets,
      lower: hexToRgb(draft.value.lower) ? [hexToRgb(draft.value.lower)] : [],
      upper: hexToRgb(draft.value.upper) ? [hexToRgb(draft.value.upper)] : [],
      roi: parseRoi(),
      threshold: draft.value.threshold,
    })
    update({ result })
  } catch (error) {
    update({ error: error?.message || '识图执行失败' })
  }
}

function close() {
  props.modalId && actions.closeModal?.(props.modalId)
}
</script>

<template>
  <div class="recognition-debug-modal">
    <div class="recognition-toolbar">
      <n-select :value="draft.kind" :options="imageKinds" style="width: 180px;" @update:value="value => update({ kind: value, result: null })" />
      <n-button @click="useNewScreenshot">新截图</n-button>
      <n-button :disabled="!state.screenshotBase64.value" @click="useCurrentScreenshot">使用截图工具图片</n-button>
      <n-button @click="clearImage" :disabled="!imageUrl && !selectedResourceUrl">清除图片</n-button>
      <n-button type="primary" :disabled="!hasTestImage" :loading="state.loading.value" @click="runRecognition">开始识图</n-button>
    </div>

    <div class="recognition-layout">
      <div class="recognition-settings">
        <n-text strong>测试图片</n-text>
        <div v-if="recognitionResourceOptions.length" class="resource-picker-field">
          <n-input :value="draft.imagePath" readonly placeholder="未选择测试图片" />
          <n-button @click="openImageResourcePicker">选择</n-button>
        </div>
        <n-empty v-else description="项目暂无图片资源" size="small" />

        <template v-if="draft.kind === 'ocr'">
          <n-text strong>期望文本</n-text>
          <n-input :value="draft.expected" placeholder="可选，例如：确认" @update:value="value => update({ expected: value })" />
        </template>
        <template v-else-if="draft.kind === 'template' || draft.kind === 'feature'">
          <n-text strong>模板资源</n-text>
          <div class="resource-picker-field">
            <n-input :value="draft.templatePath" readonly placeholder="未选择模板资源，例如 assets:template.png" />
            <n-button @click="openTemplateResourcePicker">选择</n-button>
          </div>
          <n-input-number v-if="draft.kind === 'template'" :value="draft.threshold" :min="0" :max="1" :step="0.01" style="width: 100%;" @update:value="value => update({ threshold: value })" />
        </template>
        <template v-else-if="draft.kind === 'nnd'">
          <n-text strong>模型资源</n-text>
          <n-select
            :value="draft.modelPath"
            :options="modelOptions"
            placeholder="选择项目声明的 NND 模型"
            filterable
            clearable
            @update:value="value => update({ modelPath: value })"
          />
          <n-text v-if="!modelOptions.length" type="warning">项目中没有声明或发现可用的 NND 模型。</n-text>
          <n-input :value="draft.targets" placeholder="目标标签，可用 | 分隔" @update:value="value => update({ targets: value })" />
        </template>
        <template v-else-if="draft.kind === 'color'">
          <n-text strong>颜色范围</n-text>
          <n-space>
            <n-input :value="draft.lower" placeholder="#000000" @update:value="value => update({ lower: value })" />
            <n-input :value="draft.upper" placeholder="#ffffff" @update:value="value => update({ upper: value })" />
          </n-space>
        </template>
        <div class="roi-editor">
          <div class="roi-heading">
            <n-text strong>识别选区</n-text>
            <n-button size="tiny" secondary :disabled="!hasRoi" @click="clearRoi">清除选区</n-button>
          </div>
          <n-grid :cols="2" :x-gap="8" :y-gap="8">
            <n-grid-item>
              <n-text depth="3">X</n-text>
              <n-input-number :value="draft.roiX" :min="0" placeholder="全图" style="width: 100%;" @update:value="value => updateRoiField('roiX', value)" />
            </n-grid-item>
            <n-grid-item>
              <n-text depth="3">Y</n-text>
              <n-input-number :value="draft.roiY" :min="0" placeholder="全图" style="width: 100%;" @update:value="value => updateRoiField('roiY', value)" />
            </n-grid-item>
            <n-grid-item>
              <n-text depth="3">宽</n-text>
              <n-input-number :value="draft.roiWidth" :min="0" placeholder="全图" style="width: 100%;" @update:value="value => updateRoiField('roiWidth', value)" />
            </n-grid-item>
            <n-grid-item>
              <n-text depth="3">高</n-text>
              <n-input-number :value="draft.roiHeight" :min="0" placeholder="全图" style="width: 100%;" @update:value="value => updateRoiField('roiHeight', value)" />
            </n-grid-item>
          </n-grid>
        </div>
        <div class="recognition-result">
          <div class="recognition-result-heading">
            <n-text strong>识图结果</n-text>
            <n-tag v-if="draft.error" type="error">执行失败</n-tag>
            <n-tag v-else-if="draft.result" :type="draft.result.hit ? 'success' : 'warning'">
              {{ draft.result.hit ? '命中' : '未命中' }}
            </n-tag>
            <n-tag v-else>等待识别</n-tag>
          </div>
          <n-text v-if="draft.error" type="error">{{ draft.error }}</n-text>
          <n-text v-else-if="draft.result && !draft.result.hit" type="warning">
            未命中，请检查识别资源、阈值、颜色范围或重新框选 ROI。
          </n-text>
          <n-text v-if="draft.result" depth="3">{{ JSON.stringify(draft.result) }}</n-text>
          <n-text v-else-if="!draft.error" depth="3">选择测试图片并执行识别后，结果将显示在这里。</n-text>
        </div>
      </div>
      <div class="recognition-image-stage">
        <div
          v-if="activeImageUrl"
          class="recognition-image-wrap"
          :class="{ 'is-selecting': isSelecting }"
          @pointerdown="startRoiSelection"
          @pointermove="moveRoiSelection"
          @pointerup="finishRoiSelection"
          @pointercancel="finishRoiSelection"
        >
          <img ref="imageRef" :src="activeImageUrl" alt="识图测试图片" draggable="false" @load="handleImageLoad" />
          <div class="recognition-roi-box" :style="roiBoxStyle">
            <span>{{ draft.roiWidth }} × {{ draft.roiHeight }}</span>
          </div>
        </div>
        <n-empty v-else description="尚未选择测试图片" class="recognition-empty-image" />
        <div
          v-if="recognitionResourcePreviewUrl"
          class="recognition-resource-preview"
          :class="{ collapsed: resourcePreviewCollapsed }"
          @pointerdown.stop
        >
          <div class="recognition-resource-header">
            <div class="recognition-resource-title">
              <n-text strong>识图资源</n-text>
              <n-text v-if="!resourcePreviewCollapsed" depth="3" :title="draft.templatePath">{{ recognitionResourceName }}</n-text>
            </div>
            <button
              v-if="resourcePreviewCollapsed"
              class="recognition-resource-handle"
              type="button"
              :title="resourcePreviewCollapsed ? '展开识图资源' : '收起识图资源'"
              :aria-label="resourcePreviewCollapsed ? '展开识图资源' : '收起识图资源'"
              @click="resourcePreviewCollapsed = !resourcePreviewCollapsed"
            ></button>
            <button
              v-else
              class="recognition-resource-collapse"
              type="button"
              title="收起识图资源"
              aria-label="收起识图资源"
              @click="resourcePreviewCollapsed = true"
            >−</button>
          </div>
          <div v-if="!resourcePreviewCollapsed" class="recognition-resource-image-wrap">
            <img :src="recognitionResourcePreviewUrl" :alt="recognitionResourceName" draggable="false" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recognition-debug-modal { display: flex; flex-direction: column; gap: 14px; height: 100%; min-height: 520px; }
.recognition-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.recognition-layout { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: 16px; flex: 1; min-height: 0; }
.recognition-settings { display: flex; flex-direction: column; gap: 10px; overflow: auto; padding-right: 4px; }
.recognition-image-stage { position: relative; display: flex; align-items: center; justify-content: center; min-height: 360px; overflow: auto; padding: 16px; background: var(--color-surface-2); }
.recognition-image-wrap { position: relative; display: inline-block; max-width: 100%; max-height: 100%; line-height: 0; cursor: crosshair; touch-action: none; }
.recognition-image-wrap.is-selecting { user-select: none; }
.recognition-image-stage img { display: block; max-width: 100%; max-height: calc(100vh - 260px); object-fit: contain; }
.recognition-roi-box { position: absolute; border: 2px solid var(--color-info); background: color-mix(in srgb, var(--color-info) 18%, transparent); pointer-events: none; }
.recognition-roi-box span { position: absolute; left: -2px; top: -24px; padding: 2px 5px; border-radius: 3px; color: white; background: var(--color-info); font-size: 11px; line-height: 16px; white-space: nowrap; }
.roi-editor { display: flex; flex-direction: column; gap: 8px; padding: 10px; border: 1px solid var(--color-border); }
.roi-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.recognition-result { display: flex; flex-direction: column; gap: 8px; min-height: 92px; padding: 10px; border: 1px solid var(--color-border); word-break: break-all; }
.recognition-result-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.resource-picker-field { display: flex; gap: 8px; align-items: center; }
.resource-picker-field .n-input { min-width: 0; flex: 1; }
.recognition-empty-image { margin: auto; }
.recognition-resource-preview { position: absolute; right: 12px; bottom: 12px; z-index: 3; display: flex; flex-direction: column; width: min(240px, calc(100% - 24px)); max-height: 44%; overflow: hidden; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-surface); box-shadow: 0 8px 24px var(--color-shadow); }
.recognition-resource-preview.collapsed { right: 0; bottom: 24px; width: 142px; border-right: 0; border-radius: 6px 0 0 6px; }
.recognition-resource-header { display: flex; align-items: center; justify-content: space-between; min-height: 34px; gap: 8px; padding: 5px 7px 5px 10px; }
.recognition-resource-handle { position: absolute; top: 50%; right: -1px; width: 8px; height: 76px; padding: 0; border: 0; border-radius: 8px 0 0 8px; background: #ef4444; box-shadow: 0 0 0 1px color-mix(in srgb, #ef4444 70%, transparent), 0 3px 10px color-mix(in srgb, #ef4444 45%, transparent); transform: translateY(-50%); cursor: grab; }
.recognition-resource-handle::before, .recognition-resource-handle::after { position: absolute; left: -3px; width: 14px; height: 14px; border-radius: 50%; background: #ef4444; content: ''; }
.recognition-resource-handle::before { top: -2px; }
.recognition-resource-handle::after { bottom: -2px; }
.recognition-resource-handle:hover { background: #dc2626; }
.recognition-resource-collapse { display: grid; place-items: center; flex: 0 0 22px; width: 22px; height: 22px; padding: 0; border: 0; border-radius: 50%; color: var(--color-text-secondary); background: var(--color-surface-2); cursor: pointer; }
.recognition-resource-collapse:hover { color: var(--color-text-primary); background: var(--color-button-hover); }
.recognition-resource-title { display: flex; align-items: baseline; min-width: 0; gap: 7px; }
.recognition-resource-title .n-text:last-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.recognition-resource-image-wrap { display: flex; align-items: center; justify-content: center; min-height: 90px; overflow: auto; padding: 8px; border-top: 1px solid var(--color-border); background: var(--color-surface-2); }
.recognition-resource-image-wrap img { display: block; width: auto; height: auto; max-width: 100%; max-height: 180px; object-fit: contain; }
@media (max-width: 760px) { .recognition-layout { grid-template-columns: 1fr; } .recognition-image-stage { min-height: 260px; } }
</style>
