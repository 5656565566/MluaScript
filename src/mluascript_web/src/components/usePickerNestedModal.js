import { openModal } from '../modalStore'

export function usePickerNestedModal(props, state, deps = {}) {
  const {
    effectiveHandlers,
    formValues,
    persistModalProps,
  } = state

  const {
    AsyncPickerModalShell,
    SharedVariableManagerModal,
  } = deps

  function openInlineFieldPicker(field) {
    const fieldKey = field?.key
    if (!fieldKey) return

    if (typeof effectiveHandlers.value.onOpenFieldPicker === 'function') {
      effectiveHandlers.value.onOpenFieldPicker(fieldKey, { ...formValues.value })
      return
    }

    const pickerConfig = field?.picker
    if (!pickerConfig) return

    openModal({
      type: 'blockly-picker',
      component: AsyncPickerModalShell,
      parentId: props.modalId,
      props: {
        ...pickerConfig,
        currentValue: formValues.value[fieldKey] || null,
        keepOpenOnSelect: true,
        onSelect: (selectedValue) => {
          formValues.value = { ...formValues.value, [fieldKey]: selectedValue }
          persistModalProps({ currentValue: { ...formValues.value } })
        },
      },
      options: {
        title: pickerConfig.title || '选择',
        size: pickerConfig.form ? 'xl' : 'lg',
        panelClass: 'picker-modal-panel',
        contentClass: 'picker-modal-content-wrap',
        showClose: true,
      },
    })
  }

  function openSharedVariableManager() {
    openModal({
      type: 'shared-variable-manager',
      component: SharedVariableManagerModal,
      parentId: props.modalId,
      props: {},
      options: {
        title: '管理全局状态',
        size: 'lg',
        panelClass: 'shared-variable-modal-panel',
        contentClass: 'shared-variable-modal-content-wrap',
        showClose: true,
      },
    })
  }

  return {
    openInlineFieldPicker,
    openSharedVariableManager,
  }
}
