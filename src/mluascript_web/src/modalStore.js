import { computed, ref, watch } from 'vue'

const MODAL_Z_INDEX_BASE = 2000
const MODAL_Z_INDEX_STEP = 10

const modalStack = ref([])
let modalIdSeed = 0

function nextModalId(type = 'modal') {
  modalIdSeed += 1
  return `${type}-${Date.now()}-${modalIdSeed}`
}

function normalizeModalOptions(options = {}) {
  return {
    title: options.title || '',
    size: options.size || 'md',
    panelClass: options.panelClass || '',
    contentClass: options.contentClass || '',
    closeOnEsc: options.closeOnEsc !== false,
    closeOnBackdrop: options.closeOnBackdrop !== false,
    showClose: options.showClose !== false,
    lockScroll: options.lockScroll !== false,
    trapFocus: options.trapFocus !== false,
    destroyOnClose: options.destroyOnClose !== false,
    ...options,
  }
}

function findModalIndex(modalId) {
  return modalStack.value.findIndex((item) => item.id === modalId)
}

function collectDescendantIds(parentId) {
  const result = []
  const queue = [parentId]

  while (queue.length) {
    const currentId = queue.shift()
    const children = modalStack.value.filter((item) => item.parentId === currentId)
    for (const child of children) {
      result.push(child.id)
      queue.push(child.id)
    }
  }

  return result
}

function toggleBodyScrollLock() {
  if (typeof document === 'undefined') return
  const hasLockingModal = modalStack.value.some((item) => item.options.lockScroll)
  document.body.classList.toggle('modal-open', hasLockingModal)
}

watch(modalStack, () => {
  toggleBodyScrollLock()
}, { deep: true })

export const modalState = {
  modalStack,
  topModalId: computed(() => modalStack.value[modalStack.value.length - 1]?.id || null),
  hasModal: computed(() => modalStack.value.length > 0),
}

export function getModalZIndex(index) {
  return MODAL_Z_INDEX_BASE + index * MODAL_Z_INDEX_STEP
}

export function openModal({
  type,
  component,
  props = {},
  parentId = null,
  options = {},
} = {}) {
  if (!type) throw new Error('openModal 缺少 type')
  if (!component) throw new Error(`openModal(${type}) 缺少 component`)

  const instance = {
    id: nextModalId(type),
    type,
    component,
    parentId,
    props: { ...props },
    options: normalizeModalOptions(options),
    openedAt: Date.now(),
  }

  modalStack.value = [...modalStack.value, instance]
  return instance.id
}

export function closeModal(modalId) {
  if (!modalId) return
  const idsToRemove = new Set([modalId, ...collectDescendantIds(modalId)])
  modalStack.value = modalStack.value.filter((item) => !idsToRemove.has(item.id))
}

export function closeTopModal() {
  const topId = modalState.topModalId.value
  if (topId) closeModal(topId)
}

export function closeChildModals(parentId) {
  if (!parentId) return
  const childIds = modalStack.value.filter((item) => item.parentId === parentId).map((item) => item.id)
  const idsToRemove = new Set()
  for (const childId of childIds) {
    idsToRemove.add(childId)
    for (const descendantId of collectDescendantIds(childId)) {
      idsToRemove.add(descendantId)
    }
  }
  modalStack.value = modalStack.value.filter((item) => !idsToRemove.has(item.id))
}

export function updateModalProps(modalId, patch = {}) {
  const index = findModalIndex(modalId)
  if (index === -1) return
  const current = modalStack.value[index]
  const next = {
    ...current,
    props: {
      ...current.props,
      ...patch,
    },
  }
  modalStack.value = [
    ...modalStack.value.slice(0, index),
    next,
    ...modalStack.value.slice(index + 1),
  ]
}

export function replaceModalProps(modalId, nextProps = {}) {
  const index = findModalIndex(modalId)
  if (index === -1) return
  const current = modalStack.value[index]
  const next = {
    ...current,
    props: { ...nextProps },
  }
  modalStack.value = [
    ...modalStack.value.slice(0, index),
    next,
    ...modalStack.value.slice(index + 1),
  ]
}

export function updateModalOptions(modalId, patch = {}) {
  const index = findModalIndex(modalId)
  if (index === -1) return
  const current = modalStack.value[index]
  const next = {
    ...current,
    options: normalizeModalOptions({
      ...current.options,
      ...patch,
    }),
  }
  modalStack.value = [
    ...modalStack.value.slice(0, index),
    next,
    ...modalStack.value.slice(index + 1),
  ]
}

export function getModalInstance(modalId) {
  return modalStack.value.find((item) => item.id === modalId) || null
}

export function clearAllModals() {
  modalStack.value = []
}
