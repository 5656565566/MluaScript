<script setup>
import { ChevronDownOutline } from '@vicons/ionicons5'
import { NButton, NDropdown, NIcon } from 'naive-ui'

defineProps({
  label: { type: String, required: true },
  onSelect: { type: Function, required: true },
  modalId: { type: String, default: '' },
})

const options = [
  { label: '截图预览', key: 'screenshot' },
  { label: '识图调试', key: 'recognition' },
]
</script>

<template>
  <div class="vision-dialog-header">
    <span>{{ label }}</span>
    <n-dropdown trigger="click" :options="options" @select="(key) => onSelect(key, modalId)">
      <n-button quaternary circle size="small" title="切换视觉工具" aria-label="切换视觉工具">
        <n-icon size="16"><ChevronDownOutline /></n-icon>
      </n-button>
    </n-dropdown>
  </div>
</template>

<style scoped>
.vision-dialog-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  color: var(--n-title-text-color);
  font-weight: 600;
}
</style>
