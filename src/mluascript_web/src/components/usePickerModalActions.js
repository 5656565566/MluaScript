import { closeModal, openModal, closeChildModals } from '../modalStore'

export function usePickerModalActions(props, state) {
  const {
    storeSnapshot,
    effectiveForm,
    effectiveHandlers,
    effectiveMultiple,
    selectedItems,
    selectedItem,
    formValues,
    createValue,
    createError,
    persistModalProps,
  } = state

  function confirmSelection() {
    let shouldCloseCurrent = !Boolean(storeSnapshot.value?.visible ? storeSnapshot.value.keepOpenOnSelect : props.keepOpenOnSelect)
    let afterConfirm = null

    if (effectiveForm.value) {
      if (typeof effectiveHandlers.value.onConfirm === 'function') {
        const result = effectiveHandlers.value.onConfirm({ ...formValues.value })
        if (result && typeof result === 'object') {
          if (Object.prototype.hasOwnProperty.call(result, 'close')) shouldCloseCurrent = Boolean(result.close)
          if (typeof result.afterConfirm === 'function') afterConfirm = result.afterConfirm
        } else if (result === false) {
          shouldCloseCurrent = false
        }
      } else if (typeof effectiveHandlers.value.onSelect === 'function') {
        const result = effectiveHandlers.value.onSelect({ ...formValues.value })
        if (result === false) shouldCloseCurrent = false
      }
    } else if (effectiveMultiple.value) {
      if (typeof effectiveHandlers.value.onSelect === 'function') {
        const result = effectiveHandlers.value.onSelect([...selectedItems.value])
        if (result === false) shouldCloseCurrent = false
      }
    } else if (selectedItem.value !== null) {
      if (typeof effectiveHandlers.value.onSelect === 'function') {
        const result = effectiveHandlers.value.onSelect(selectedItem.value)
        if (result === false) shouldCloseCurrent = false
      }
    }

    if (shouldCloseCurrent) {
      closeChildModals(props.modalId)
      closeModal(props.modalId)
    }

    if (typeof afterConfirm === 'function') {
      afterConfirm()
    }
  }

  function cancelSelection() {
    closeModal(props.modalId)
  }

  function handleCreate() {
    if (typeof effectiveHandlers.value.onCreate !== 'function') return
    try {
      const maybeNextItems = effectiveHandlers.value.onCreate(createValue.value)
      if (Array.isArray(maybeNextItems)) {
        persistModalProps({ items: maybeNextItems, currentValue: selectedItem.value })
      }
      createValue.value = ''
      createError.value = ''
    } catch (error) {
      createError.value = error.message || '创建失败'
    }
  }

  function handleManage(fallback) {
    if (typeof effectiveHandlers.value.onManage === 'function') {
      effectiveHandlers.value.onManage()
      return
    }
    if (typeof fallback === 'function') {
      fallback()
    }
  }

  function openChildPicker(config = {}) {
    openModal(config)
  }

  return {
    confirmSelection,
    cancelSelection,
    handleCreate,
    handleManage,
    openChildPicker,
  }
}
