import { computed, ref } from 'vue'
import { closeModal, getModalInstance, openModal, updateModalProps, updateModalOptions } from '../modalStore'
import PickerModalShell from '../components/PickerModalShell.vue'

const initialState = () => ({
  modalId: null,
  visible: false,
  title: '选择',
  subtitle: '',
  summary: '',
  items: [],
  currentValue: null,
  multiple: false,
  allowCreate: false,
  createButtonText: '新建',
  createPlaceholder: '输入名称',
  manageButtonText: '管理',
  emptyText: '暂无可选项',
  keepOpenOnSelect: false,
  form: null,
  functionArgs: [],
  context: null,
  handlers: {
    onSelect: null,
    onConfirm: null,
    onCreate: null,
    onManage: null,
    onOpenFieldPicker: null,
  },
})

const pickerStateRef = ref(initialState())

function asNonEmptyString(value, fallback = '') {
  const normalized = String(value || '').trim()
  return normalized || fallback
}

function normalizePickerItem(item) {
  if (!item || typeof item !== 'object') return null
  const value = asNonEmptyString(item.value ?? item.name ?? item.label)
  const label = asNonEmptyString(item.label ?? item.name ?? value, value)
  if (!value && !label) return null
  return {
    ...item,
    value: value || label,
    label: label || value,
    description: asNonEmptyString(item.description),
    group: asNonEmptyString(item.group),
  }
}

function normalizePickerItems(items) {
  if (!Array.isArray(items)) return []
  return items.map(normalizePickerItem).filter(Boolean)
}

function normalizePickerConfig(config = {}) {
  const normalized = config && typeof config === 'object' ? config : {}
  return {
    title: asNonEmptyString(normalized.title, '选择'),
    subtitle: asNonEmptyString(normalized.subtitle),
    summary: asNonEmptyString(normalized.summary),
    items: normalizePickerItems(normalized.items),
    currentValue: normalized.currentValue ?? null,
    multiple: Boolean(normalized.multiple),
    allowCreate: Boolean(normalized.allowCreate),
    createButtonText: asNonEmptyString(normalized.createButtonText, '新建'),
    createPlaceholder: asNonEmptyString(normalized.createPlaceholder, '输入名称'),
    manageButtonText: asNonEmptyString(normalized.manageButtonText, '管理'),
    emptyText: asNonEmptyString(normalized.emptyText, '暂无可选项'),
    keepOpenOnSelect: Boolean(normalized.keepOpenOnSelect),
    form: normalized.form && typeof normalized.form === 'object' ? normalized.form : null,
    functionArgs: Array.isArray(normalized.functionArgs) ? normalized.functionArgs : [],
    context: normalized.context && typeof normalized.context === 'object' ? normalized.context : null,
    handlers: {
      onSelect: typeof normalized.onSelect === 'function' ? normalized.onSelect : null,
      onConfirm: typeof normalized.onConfirm === 'function' ? normalized.onConfirm : null,
      onCreate: typeof normalized.onCreate === 'function' ? normalized.onCreate : null,
      onManage: typeof normalized.onManage === 'function' ? normalized.onManage : null,
      onOpenFieldPicker: typeof normalized.onOpenFieldPicker === 'function' ? normalized.onOpenFieldPicker : null,
    },
  }
}

function buildModalProps(snapshot) {
  return {
    modalId: snapshot.modalId,
    title: snapshot.title,
    subtitle: snapshot.subtitle,
    summary: snapshot.summary,
    items: snapshot.items,
    currentValue: snapshot.currentValue,
    multiple: snapshot.multiple,
    allowCreate: snapshot.allowCreate,
    createButtonText: snapshot.createButtonText,
    createPlaceholder: snapshot.createPlaceholder,
    manageButtonText: snapshot.manageButtonText,
    emptyText: snapshot.emptyText,
    keepOpenOnSelect: snapshot.keepOpenOnSelect,
    form: snapshot.form,
    functionArgs: snapshot.functionArgs,
    onSelect: snapshot.handlers.onSelect,
    onConfirm: snapshot.handlers.onConfirm,
    onCreate: snapshot.handlers.onCreate,
    onManage: snapshot.handlers.onManage,
    onOpenFieldPicker: snapshot.handlers.onOpenFieldPicker,
  }
}

function syncModal(snapshot = pickerStateRef.value) {
  if (!snapshot.modalId) return
  updateModalProps(snapshot.modalId, buildModalProps(snapshot))
  updateModalOptions(snapshot.modalId, {
    title: snapshot.title,
    size: snapshot.form ? 'xl' : 'lg',
    panelClass: 'picker-modal-panel',
    contentClass: 'picker-modal-content-wrap',
    showClose: true,
  })
}

export const pickerState = {
  snapshot: pickerStateRef,
  visible: computed(() => pickerStateRef.value.visible),
  modalId: computed(() => pickerStateRef.value.modalId),
  items: computed(() => pickerStateRef.value.items),
  currentValue: computed(() => pickerStateRef.value.currentValue),
  context: computed(() => pickerStateRef.value.context),
}

export const pickerActions = {
  open(config = {}) {
    const normalized = normalizePickerConfig(config)
    const currentModalId = pickerStateRef.value.modalId
    const existingModal = currentModalId ? getModalInstance(currentModalId) : null
    const nextState = {
      ...initialState(),
      ...normalized,
      visible: true,
      modalId: existingModal ? currentModalId : null,
    }

    if (!nextState.modalId) {
      const modalId = openModal({
        type: 'blockly-picker',
        component: PickerModalShell,
        props: buildModalProps(nextState),
        options: {
          title: nextState.title,
          size: nextState.form ? 'xl' : 'lg',
          panelClass: 'picker-modal-panel',
          contentClass: 'picker-modal-content-wrap',
          showClose: true,
        },
      })
      nextState.modalId = modalId
    }

    pickerStateRef.value = nextState
    syncModal(nextState)
    return nextState.modalId
  },

  update(patch = {}) {
    if (!pickerStateRef.value.modalId) return
    const merged = normalizePickerConfig({
      ...pickerStateRef.value,
      ...patch,
      onSelect: patch.onSelect ?? pickerStateRef.value.handlers.onSelect,
      onConfirm: patch.onConfirm ?? pickerStateRef.value.handlers.onConfirm,
      onCreate: patch.onCreate ?? pickerStateRef.value.handlers.onCreate,
      onManage: patch.onManage ?? pickerStateRef.value.handlers.onManage,
      onOpenFieldPicker: patch.onOpenFieldPicker ?? pickerStateRef.value.handlers.onOpenFieldPicker,
    })
    pickerStateRef.value = {
      ...pickerStateRef.value,
      ...merged,
      visible: true,
      modalId: pickerStateRef.value.modalId,
    }
    syncModal()
  },

  close() {
    const modalId = pickerStateRef.value.modalId
    if (modalId) {
      closeModal(modalId)
    }
    pickerStateRef.value = initialState()
  },

  setItems(items, currentValue = pickerStateRef.value.currentValue) {
    if (!pickerStateRef.value.modalId) return
    pickerStateRef.value = {
      ...pickerStateRef.value,
      items: normalizePickerItems(items),
      currentValue,
    }
    syncModal()
  },

  setCurrentValue(currentValue) {
    if (!pickerStateRef.value.modalId) return
    pickerStateRef.value = {
      ...pickerStateRef.value,
      currentValue,
    }
    syncModal()
  },
}
