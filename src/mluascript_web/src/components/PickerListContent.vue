<script setup>
import { computed, ref, watch } from 'vue'
import { NButton, NInput, NText, NCard, NTag, NEmpty, NPagination, NIcon } from 'naive-ui'
import { ChevronForwardOutline, DocumentOutline, FolderOutline, HomeOutline } from '@vicons/ionicons5'

const props = defineProps({
  title: { type: String, default: '选择' },
  subtitle: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  selectedValue: { type: [String, Number, Boolean, null], default: null },
  selectedValues: { type: Array, default: () => [] },
  multiple: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无可选项' },
  searchQuery: { type: String, default: '' },
  allowCreate: { type: Boolean, default: false },
  createValue: { type: String, default: '' },
  createError: { type: String, default: '' },
  createButtonText: { type: String, default: '新建' },
  createPlaceholder: { type: String, default: '输入名称' },
  manageButtonText: { type: String, default: '管理' },
  showManageButton: { type: Boolean, default: false },
  treeMode: { type: Boolean, default: false },
})

const emit = defineEmits(['update:searchQuery', 'update:createValue', 'select', 'create', 'manage'])
const page = ref(1)
const PAGE_SIZE = 12
const navigationPath = ref([])

const filteredItems = computed(() => {
  const query = props.searchQuery.trim().toLowerCase()
  if (!query) return props.items
  return props.items.filter((item) => {
    const label = String(item.label || item.value || '').toLowerCase()
    const value = String(item.value || '').toLowerCase()
    return label.includes(query) || value.includes(query)
  })
})
const pageCount = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / PAGE_SIZE)))
const pageItems = computed(() => filteredItems.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
const navigationNodes = computed(() => {
  if (props.searchQuery.trim()) {
    return filteredItems.value.map(item => ({
      key: item.value,
      label: item.label,
      kind: 'file',
      item,
    }))
  }

  const current = navigationPath.value
  const nodes = new Map()
  for (const item of filteredItems.value) {
    const [domain, ...relativeParts] = String(item.value || '').split(':')
    const segments = [domain, ...relativeParts.join(':').split('/').filter(Boolean)]
    if (segments.length <= current.length || !current.every((segment, index) => segments[index] === segment)) continue
    const nextSegment = segments[current.length]
    const isFile = segments.length === current.length + 1
    const nextPath = [...current, nextSegment]
    const key = nextPath.join('/')
    if (!nodes.has(key)) {
      nodes.set(key, {
        key,
        label: nextSegment,
        kind: isFile ? 'file' : 'directory',
        item: isFile ? item : null,
      })
    }
  }
  return [...nodes.values()].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === 'directory' ? -1 : 1
    return left.label.localeCompare(right.label, 'zh-Hans-CN')
  })
})
const navigationPageCount = computed(() => Math.max(1, Math.ceil(navigationNodes.value.length / PAGE_SIZE)))
const visibleNavigationNodes = computed(() => navigationNodes.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

watch(() => props.searchQuery, () => { page.value = 1; navigationPath.value = [] })
watch([pageCount, navigationPageCount], () => {
  page.value = Math.min(page.value, props.treeMode ? navigationPageCount.value : pageCount.value)
})

const selectedItemMeta = computed(() => props.items.find(item => item.value === props.selectedValue) || null)
const selectedItemMetas = computed(() => props.selectedValues.map(value => props.items.find(item => item.value === value)).filter(Boolean))

function isSelected(itemValue) {
  return props.multiple ? props.selectedValues.includes(itemValue) : props.selectedValue === itemValue
}

function openNavigationNode(node) {
  if (node.kind === 'directory') {
    navigationPath.value = node.key.split('/')
    page.value = 1
    return
  }
  emit('select', node.item)
}

function navigateTo(index) {
  navigationPath.value = index < 0 ? [] : navigationPath.value.slice(0, index + 1)
  page.value = 1
}
</script>

<template>
  <div class="picker-list-content">
    <n-text v-if="subtitle" depth="3" class="picker-list-context">{{ subtitle }}</n-text>
    <n-input
      :value="searchQuery"
      :placeholder="`搜索${title}...`"
      style="margin-bottom: 16px;"
      autofocus
      clearable
      size="large"
      @update:value="value => emit('update:searchQuery', value)"
    />

    <div style="margin-bottom: 16px; padding: 12px 16px; border: 1px solid var(--n-border-color); border-radius: 8px; background: color-mix(in srgb, var(--n-primary-color) 4%, transparent); display: flex; align-items: center; min-height: 48px;">
      <template v-if="multiple">
        <template v-if="selectedItemMetas.length">
          <n-text depth="3" style="font-size: 12px; margin-right: 12px; flex-shrink: 0;">当前已选</n-text>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <n-tag v-for="item in selectedItemMetas" :key="item.value" type="primary" round>{{ item.label }}</n-tag>
          </div>
        </template>
        <n-text v-else depth="3" style="font-size: 13px;">请选择一个或多个项目后再确认</n-text>
      </template>
      <template v-else-if="selectedItemMeta">
        <n-text depth="3" style="font-size: 12px; margin-right: 12px; flex-shrink: 0;">当前选择</n-text>
        <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
          <n-text strong>{{ selectedItemMeta.label }}</n-text>
          <n-text v-if="selectedItemMeta.description" depth="3" style="font-size: 12px; word-break: break-all;">{{ selectedItemMeta.description }}</n-text>
        </div>
      </template>
      <n-text v-else depth="3" style="font-size: 13px;">请选择一项后再确认</n-text>
    </div>

    <div v-if="allowCreate" style="display: flex; gap: 8px; margin-bottom: 12px; align-items: flex-start;">
      <div style="flex: 1; display: flex; flex-direction: column; gap: 6px;">
        <n-input
          :value="createValue"
          :placeholder="createPlaceholder"
          @keyup.enter="emit('create')"
          @update:value="value => emit('update:createValue', value)"
        />
        <n-text v-if="createError" type="error" style="font-size: 12px;">{{ createError }}</n-text>
      </div>
      <n-button @click="emit('create')">{{ createButtonText }}</n-button>
    </div>

    <div v-if="showManageButton" style="display: flex; gap: 8px; margin-bottom: 12px;">
      <n-button quaternary @click="emit('manage')">{{ manageButtonText }}</n-button>
    </div>

    <div v-if="treeMode" class="picker-list-scroll picker-tree-scroll">
      <div class="picker-file-browser-toolbar">
        <div class="picker-file-browser-breadcrumb">
          <n-button quaternary size="small" title="资源根目录" aria-label="资源根目录" @click="navigateTo(-1)">
            <template #icon><n-icon><home-outline /></n-icon></template>
            resources
          </n-button>
          <template v-for="(segment, index) in navigationPath" :key="`${segment}-${index}`">
            <n-icon depth="3" size="14"><chevron-forward-outline /></n-icon>
            <n-button quaternary size="small" @click="navigateTo(index)">{{ segment }}</n-button>
          </template>
        </div>
      </div>
      <div
        v-for="node in visibleNavigationNodes"
        :key="node.key"
        class="picker-file-browser-row"
        :class="{ selected: node.item && isSelected(node.item.value) }"
        @click="openNavigationNode(node)"
      >
        <n-icon class="picker-file-browser-icon" size="19">
          <folder-outline v-if="node.kind === 'directory'" />
          <document-outline v-else />
        </n-icon>
        <div class="picker-file-browser-label">
          <n-text strong>{{ node.label }}</n-text>
        </div>
        <n-icon v-if="node.kind === 'directory'" depth="3" size="16"><chevron-forward-outline /></n-icon>
      </div>
      <n-empty v-if="!visibleNavigationNodes.length" :description="emptyText" style="margin: 40px 0;" />
    </div>
    <div v-else class="picker-list-scroll">
      <n-card
        v-for="item in pageItems"
        :key="item.value"
        size="small"
        hoverable
        style="cursor: pointer;"
        :style="isSelected(item.value) ? 'border-color: var(--n-primary-color); background: color-mix(in srgb, var(--n-primary-color) 8%, transparent);' : ''"
        @click="emit('select', item)"
      >
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
          <div style="min-width: 0;">
            <n-text strong>{{ item.label }}</n-text>
            <n-text v-if="item.description" depth="3" style="display: block; margin-top: 4px; font-size: 12px; word-break: break-all;">{{ item.description }}</n-text>
          </div>
          <n-tag v-if="item.group" size="small" :bordered="false">{{ item.group }}</n-tag>
        </div>
      </n-card>
      <n-empty v-if="!filteredItems.length" :description="emptyText" style="margin: 40px 0;" />
    </div>
    <n-pagination v-if="treeMode ? navigationNodes.length : pageItems.length" v-model:page="page" :page-count="treeMode ? navigationPageCount : pageCount" simple style="justify-content: flex-end; margin-top: 12px;" />
  </div>
</template>

<style scoped src="./pickerListContent.css"></style>
