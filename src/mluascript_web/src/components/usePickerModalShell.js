import { computed, ref } from 'vue'
import { updateModalProps } from '../modalStore'
import { pickerActions, pickerState } from '../store/pickerState'

export function usePickerModalShell(props) {
  const searchQuery = ref('')
  const selectedItem = ref(null)
  const selectedItems = ref([])
  const createValue = ref('')
  const createError = ref('')
  const formValues = ref({})

  const storeSnapshot = computed(() => pickerState.snapshot.value || null)
  const isStoreDriven = computed(() => Boolean(storeSnapshot.value?.visible && storeSnapshot.value?.modalId === props.modalId))

  const effectiveItems = computed(() => {
    const storeItems = storeSnapshot.value?.items
    if (isStoreDriven.value && Array.isArray(storeItems)) return storeItems
    return Array.isArray(props.items) ? props.items : []
  })

  const effectiveTitle = computed(() => isStoreDriven.value ? (storeSnapshot.value?.title || props.title) : props.title)
  const effectiveSubtitle = computed(() => isStoreDriven.value ? (storeSnapshot.value?.subtitle || props.subtitle) : props.subtitle)
  const effectiveEmptyText = computed(() => isStoreDriven.value ? (storeSnapshot.value?.emptyText || props.emptyText) : props.emptyText)
  const effectiveAllowCreate = computed(() => {
    if (isStoreDriven.value) return Boolean(storeSnapshot.value?.allowCreate)
    return props.allowCreate
  })
  const effectiveCreateButtonText = computed(() => isStoreDriven.value ? (storeSnapshot.value?.createButtonText || props.createButtonText) : props.createButtonText)
  const effectiveCreatePlaceholder = computed(() => isStoreDriven.value ? (storeSnapshot.value?.createPlaceholder || props.createPlaceholder) : props.createPlaceholder)
  const effectiveManageButtonText = computed(() => isStoreDriven.value ? (storeSnapshot.value?.manageButtonText || props.manageButtonText) : props.manageButtonText)
  const effectiveMultiple = computed(() => {
    if (isStoreDriven.value) return Boolean(storeSnapshot.value?.multiple)
    return props.multiple
  })
  const effectiveCurrentValue = computed(() => {
    if (isStoreDriven.value) return storeSnapshot.value?.currentValue ?? null
    return props.currentValue
  })
  const effectiveSummary = computed(() => isStoreDriven.value ? (storeSnapshot.value?.summary || props.summary) : props.summary)
  const effectiveForm = computed(() => {
    if (isStoreDriven.value && storeSnapshot.value?.form) return storeSnapshot.value.form
    return props.form
  })
  const effectiveHandlers = computed(() => ({
    // Store 快照是当前步骤的完整状态；显式 null 不能回退到弹窗初始 props 的旧处理器。
    onSelect: isStoreDriven.value ? storeSnapshot.value?.handlers?.onSelect : props.onSelect,
    onConfirm: isStoreDriven.value ? storeSnapshot.value?.handlers?.onConfirm : props.onConfirm,
    onCreate: isStoreDriven.value ? storeSnapshot.value?.handlers?.onCreate : props.onCreate,
    onManage: isStoreDriven.value ? storeSnapshot.value?.handlers?.onManage : props.onManage,
    onOpenFieldPicker: isStoreDriven.value ? storeSnapshot.value?.handlers?.onOpenFieldPicker : props.onOpenFieldPicker,
  }))
  const showManageButton = computed(() => typeof effectiveHandlers.value.onManage === 'function')

  function initState() {
    searchQuery.value = ''
    createValue.value = ''
    createError.value = ''
    formValues.value = effectiveForm.value ? { ...(effectiveCurrentValue.value || {}) } : {}

    if (effectiveMultiple.value) {
      selectedItems.value = Array.isArray(effectiveCurrentValue.value) ? [...effectiveCurrentValue.value] : []
      selectedItem.value = null
    } else {
      selectedItem.value = effectiveCurrentValue.value ?? null
      selectedItems.value = []
    }
  }

  function persistModalProps(patch = {}) {
    updateModalProps(props.modalId, patch)
    if (isStoreDriven.value) {
      pickerActions.update(patch)
    }
  }

  function selectItem(item) {
    if (effectiveMultiple.value) {
      if (selectedItems.value.includes(item.value)) {
        selectedItems.value = selectedItems.value.filter(value => value !== item.value)
      } else {
        selectedItems.value = [...selectedItems.value, item.value]
      }
      return
    }
    selectedItem.value = item.value
  }

  function setFormValues(value) {
    formValues.value = value
  }

  function setSearchQuery(value) {
    searchQuery.value = value
  }

  function setCreateValue(value) {
    createValue.value = value
  }

  return {
    searchQuery,
    selectedItem,
    selectedItems,
    createValue,
    createError,
    formValues,
    storeSnapshot,
    isStoreDriven,
    effectiveItems,
    effectiveTitle,
    effectiveSubtitle,
    effectiveEmptyText,
    effectiveAllowCreate,
    effectiveCreateButtonText,
    effectiveCreatePlaceholder,
    effectiveManageButtonText,
    effectiveMultiple,
    effectiveCurrentValue,
    effectiveSummary,
    effectiveForm,
    effectiveHandlers,
    showManageButton,
    initState,
    persistModalProps,
    selectItem,
    setFormValues,
    setSearchQuery,
    setCreateValue,
  }
}
