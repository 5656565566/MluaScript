<script setup>
import { watch, defineAsyncComponent } from 'vue'
import SharedVariableManagerModal from './SharedVariableManagerModal.vue'
import PickerListContent from './PickerListContent.vue'
import PickerFormContent from './PickerFormContent.vue'
import { NButton, NAlert } from 'naive-ui'
import { usePickerModalShell } from './usePickerModalShell'
import { usePickerModalActions } from './usePickerModalActions'
import { usePickerNestedModal } from './usePickerNestedModal'

const props = defineProps({
  modalId: { type: String, required: true },
  functionArgs: { type: Array, default: () => [] },
  title: { type: String, default: '选择' },
  subtitle: { type: String, default: '' },
  summary: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  currentValue: { type: [Array, Object, String, Number, Boolean, null], default: null },
  multiple: { type: Boolean, default: false },
  allowCreate: { type: Boolean, default: false },
  createButtonText: { type: String, default: '新建' },
  createPlaceholder: { type: String, default: '输入名称' },
  manageButtonText: { type: String, default: '管理' },
  emptyText: { type: String, default: '暂无可选项' },
  keepOpenOnSelect: { type: Boolean, default: false },
  form: { type: Object, default: null },
  onSelect: { type: Function, default: null },
  onConfirm: { type: Function, default: null },
  onCreate: { type: Function, default: null },
  onManage: { type: Function, default: null },
  onOpenFieldPicker: { type: Function, default: null },
})

const AsyncPickerModalShell = defineAsyncComponent(() => import('./PickerModalShell.vue'))

const shell = usePickerModalShell(props)
const {
  searchQuery,
  selectedItem,
  selectedItems,
  createValue,
  createError,
  formValues,
  effectiveItems,
  effectiveTitle,
  effectiveEmptyText,
  effectiveAllowCreate,
  effectiveCreateButtonText,
  effectiveCreatePlaceholder,
  effectiveManageButtonText,
  effectiveMultiple,
  effectiveCurrentValue,
  effectiveSummary,
  effectiveForm,
  showManageButton,
  initState,
  setFormValues,
  setSearchQuery,
  setCreateValue,
} = shell

const actions = usePickerModalActions(props, shell)
const {
  confirmSelection,
  cancelSelection,
  handleCreate,
  handleManage,
} = actions

const nestedModal = usePickerNestedModal(props, shell, {
  AsyncPickerModalShell,
  SharedVariableManagerModal,
})
const {
  openInlineFieldPicker,
  openSharedVariableManager,
} = nestedModal

watch(() => [props.modalId, effectiveItems.value, effectiveCurrentValue.value, effectiveMultiple.value], () => {
  initState()
}, { immediate: true, deep: true })

function handleManageWithFallback() {
  handleManage(() => {
    openSharedVariableManager()
  })
}
</script>

<template>
  <div class="picker-modal-shell">
    <div class="picker-modal-body" :class="{ 'is-form': effectiveForm }">
      <n-alert v-if="effectiveSummary" type="info" :show-icon="false" style="margin-bottom: 16px;">
        {{ effectiveSummary }}
      </n-alert>

      <PickerFormContent
        v-if="effectiveForm"
        :form="effectiveForm"
        :form-values="formValues"
        @update:form-values="setFormValues"
        @open-field-picker="openInlineFieldPicker"
      />

      <PickerListContent
        v-else
        :title="effectiveTitle"
        :items="effectiveItems"
        :selected-value="selectedItem"
        :selected-values="selectedItems"
        :multiple="effectiveMultiple"
        :empty-text="effectiveEmptyText"
        :search-query="searchQuery"
        :allow-create="effectiveAllowCreate"
        :create-value="createValue"
        :create-error="createError"
        :create-button-text="effectiveCreateButtonText"
        :create-placeholder="effectiveCreatePlaceholder"
        :manage-button-text="effectiveManageButtonText"
        :show-manage-button="showManageButton"
        @update:search-query="setSearchQuery"
        @update:create-value="setCreateValue"
        @select="shell.selectItem"
        @create="handleCreate"
        @manage="handleManageWithFallback"
      />
    </div>

    <div class="picker-modal-footer">
      <n-button @click="cancelSelection">取消</n-button>
      <n-button type="primary" @click="confirmSelection">{{ effectiveForm?.confirmText || '确认' }}</n-button>
    </div>
  </div>
</template>

<style scoped src="./pickerModalShell.css"></style>
