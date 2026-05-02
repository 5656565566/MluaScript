<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { NModal, NCard } from 'naive-ui'

const props = defineProps({
  modalId: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: 'md',
  },
  zIndex: {
    type: Number,
    required: true,
  },
  closeOnEsc: {
    type: Boolean,
    default: true,
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true,
  },
  showClose: {
    type: Boolean,
    default: true,
  },
  panelClass: {
    type: [String, Array, Object],
    default: '',
  },
  contentClass: {
    type: [String, Array, Object],
    default: '',
  },
  isTopmost: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

const panelClasses = computed(() => [
  'app-modal-panel',
  `app-modal-size-${props.size}`,
  props.panelClass,
  { 'is-topmost': props.isTopmost },
])

const contentClasses = computed(() => ['app-modal-content', props.contentClass])

function requestClose(reason = 'programmatic') {
  emit('close', { id: props.modalId, reason })
}

function handleBackdropClick() {
  if (!props.closeOnBackdrop) return
  requestClose('backdrop')
}

function handleEsc(event) {
  if (!props.isTopmost || !props.closeOnEsc) return
  if (event.key === 'Escape') {
    requestClose('escape')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleEsc)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleEsc)
})
</script>

<template>
  <n-modal
    :show="true"
    :mask-closable="closeOnBackdrop"
    :close-on-esc="closeOnEsc"
    :z-index="zIndex"
    @update:show="(val) => { if (!val) requestClose('backdrop') }"
    :style="{
      width: size === 'sm' ? '520px' : size === 'md' ? '720px' : size === 'lg' ? '960px' : size === 'xl' ? '1200px' : size === 'full' ? 'calc(100vw - 32px)' : '720px',
      maxWidth: 'calc(100vw - 48px)',
      maxHeight: 'calc(100vh - 48px)',
      display: 'flex',
      flexDirection: 'column'
    }"
    :class="[panelClass]"
  >
    <n-card
      :title="title"
      :closable="showClose"
      @close="requestClose('button')"
      size="small"
      :bordered="false"
      role="dialog"
      aria-modal="true"
      style="width: 100%; height: 100%; display: flex; flex-direction: column;"
      content-style="flex: 1; min-height: 0; overflow: auto; padding: 16px;"
      header-style="padding: 16px;"
    >
      <div :class="contentClasses" style="height: 100%;">
        <slot />
      </div>
      
      <template #footer v-if="$slots.footer">
        <slot name="footer" />
      </template>
    </n-card>
  </n-modal>
</template>
