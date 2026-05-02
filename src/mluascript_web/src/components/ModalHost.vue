<script setup>
import { computed, Teleport } from 'vue'
import BaseModal from './BaseModal.vue'
import { modalState, closeModal, getModalZIndex } from '../modalStore'

const modals = computed(() => modalState.modalStack.value.map((item, index) => ({
  ...item,
  zIndex: getModalZIndex(index),
  isTopmost: modalState.topModalId.value === item.id,
})))

function handleClose(payload) {
  closeModal(payload?.id)
}
</script>

<template>
  <Teleport to="body">
    <div class="app-modal-host">
      <BaseModal
        v-for="modal in modals"
        :key="modal.id"
        :modal-id="modal.id"
        :title="modal.options.title"
        :size="modal.options.size"
        :z-index="modal.zIndex"
        :close-on-esc="modal.options.closeOnEsc"
        :close-on-backdrop="modal.options.closeOnBackdrop"
        :show-close="modal.options.showClose"
        :panel-class="modal.options.panelClass"
        :content-class="modal.options.contentClass"
        :is-topmost="modal.isTopmost"
        @close="handleClose"
      >
        <component :is="modal.component" v-bind="modal.props" :modal-id="modal.id" />
      </BaseModal>
    </div>
  </Teleport>
</template>
