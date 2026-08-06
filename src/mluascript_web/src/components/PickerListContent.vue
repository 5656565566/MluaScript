<script setup>
import { computed } from 'vue'
import { NButton, NInput, NText, NCard, NTag, NEmpty } from 'naive-ui'

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
})

const emit = defineEmits(['update:searchQuery', 'update:createValue', 'select', 'create', 'manage'])

const filteredItems = computed(() => {
  const query = props.searchQuery.trim().toLowerCase()
  if (!query) return props.items
  return props.items.filter((item) => {
    const label = String(item.label || item.value || '').toLowerCase()
    const value = String(item.value || '').toLowerCase()
    return label.includes(query) || value.includes(query)
  })
})

const selectedItemMeta = computed(() => props.items.find(item => item.value === props.selectedValue) || null)
const selectedItemMetas = computed(() => props.selectedValues.map(value => props.items.find(item => item.value === value)).filter(Boolean))

function isSelected(itemValue) {
  return props.multiple ? props.selectedValues.includes(itemValue) : props.selectedValue === itemValue
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

    <div class="picker-list-scroll">
      <n-card
        v-for="item in filteredItems"
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
  </div>
</template>

<style scoped src="./pickerListContent.css"></style>
