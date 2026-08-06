<script setup>
import { NAlert, NButton, NDrawer, NDrawerContent, NSpace, NText } from 'naive-ui'
import TextCodeEditor from './TextCodeEditor.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  code: { type: String, default: '' },
  diagnostics: { type: Array, default: () => [] },
  stale: { type: Boolean, default: false },
})

const emit = defineEmits(['update:show'])

async function copyCode() {
  await navigator.clipboard.writeText(props.code || '')
}
</script>

<template>
  <n-drawer
    :show="show"
    placement="right"
    width="min(680px, calc(100vw - 48px))"
    :mask="false"
    :mask-closable="false"
    :trap-focus="false"
    @update:show="value => emit('update:show', value)"
  >
    <n-drawer-content closable body-content-style="padding: 0; display: flex; flex-direction: column; min-height: 0;">
      <template #header>
        <n-space align="center" justify="space-between" style="width: 100%;">
          <div>
            <n-text strong>Lua 预览</n-text>
            <n-text v-if="stale" depth="3" class="preview-state">上一次成功生成结果</n-text>
          </div>
          <n-button size="small" :disabled="!code" @click="copyCode">复制</n-button>
        </n-space>
      </template>

      <n-alert
        v-if="diagnostics.length"
        :type="stale ? 'error' : 'warning'"
        :bordered="false"
        class="preview-diagnostics"
      >
        <div v-for="(diagnostic, index) in diagnostics" :key="`${diagnostic.blockId || ''}:${index}`">
          {{ diagnostic.message }}
        </div>
      </n-alert>
      <div class="preview-editor">
        <text-code-editor :model-value="code" path="generated.lua" read-only />
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.preview-state {
  margin-left: 10px;
  font-size: 12px;
}

.preview-diagnostics {
  flex: 0 0 auto;
  max-height: 160px;
  overflow: auto;
}

.preview-editor {
  flex: 1;
  min-height: 0;
}
</style>
