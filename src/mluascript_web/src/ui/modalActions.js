import { defineAsyncComponent } from 'vue'

const BlocklyWorkspaceManagerModal = defineAsyncComponent(() => import('../components/BlocklyWorkspaceManagerModal.vue'))
const CropModal = defineAsyncComponent(() => import('../components/CropModal.vue'))
const SharedVariableManagerModal = defineAsyncComponent(() => import('../components/SharedVariableManagerModal.vue'))
const TaskDetailModal = defineAsyncComponent(() => import('../components/TaskDetailModal.vue'))
const TaskTraceModal = defineAsyncComponent(() => import('../components/TaskTraceModal.vue'))
const ImageRecognitionDebugModal = defineAsyncComponent(() => import('../components/ImageRecognitionDebugModal.vue'))
const VisionDialogHeader = defineAsyncComponent(() => import('../components/VisionDialogHeader.vue'))

export function createModalActions({ state, openModal, getActions }) {
  return {
    async openSharedVariableManager() {
      return openModal({
        type: 'shared-variable-manager',
        component: SharedVariableManagerModal,
        props: {},
        options: { title: '共享变量管理', size: 'lg' },
      })
    },

    async openBlocklyWorkspaceManager() {
      return openModal({
        type: 'blockly-workspace-manager',
        component: BlocklyWorkspaceManagerModal,
        props: {},
        options: { title: 'Blockly 工作区管理', size: 'xl' },
      })
    },

    async openTaskDetailModal(taskId) {
      if (!taskId) return null
      const actions = getActions()
      state.selectedTaskId.value = taskId
      await actions.fetchTaskDetail(taskId)
      actions.startSelectedTaskStreams(taskId)
      return openModal({
        type: 'task-detail',
        component: TaskDetailModal,
        props: { taskId },
        options: {
          title: '任务详情',
          size: 'xl',
          panelClass: 'task-detail-modal-panel',
          contentClass: 'task-detail-modal-content',
        },
      })
    },

    async openTaskLogsModal(taskId) {
      if (!taskId) return null
      const actions = getActions()
      state.selectedTaskId.value = taskId
      await Promise.all([actions.fetchTaskDetail(taskId), actions.fetchTaskLogs(taskId)])
      actions.startSelectedTaskStreams(taskId)
      return openModal({
        type: 'task-logs',
        component: TaskTraceModal,
        props: { taskId, mode: 'logs' },
        options: {
          title: '任务日志',
          size: 'xl',
          panelClass: 'task-logs-modal-panel',
          contentClass: 'task-logs-modal-content',
        },
      })
    },

    async openTaskOutputModal(taskId) {
      if (!taskId) return null
      const actions = getActions()
      state.selectedTaskId.value = taskId
      await Promise.all([actions.fetchTaskDetail(taskId), actions.fetchTaskOutput(taskId)])
      actions.startSelectedTaskStreams(taskId)
      return openModal({
        type: 'task-output',
        component: TaskTraceModal,
        props: { taskId, mode: 'output' },
        options: {
          title: '任务输出',
          size: 'xl',
          panelClass: 'task-output-modal-panel',
          contentClass: 'task-output-modal-content',
        },
      })
    },

    openScreenshotPreview() {
      state.showScreenshot.value = true
    },

    openImageRecognitionDebugModal({ imagePath = '', templatePath = '' } = {}) {
      const actions = getActions()
      state.showScreenshot.value = false
      if (imagePath || templatePath) {
        state.imageRecognitionDraft.value = {
          ...state.imageRecognitionDraft.value,
          kind: templatePath ? 'template' : state.imageRecognitionDraft.value.kind,
          imagePath: imagePath || state.imageRecognitionDraft.value.imagePath,
          templatePath: templatePath || state.imageRecognitionDraft.value.templatePath,
          imageBase64: imagePath ? '' : state.imageRecognitionDraft.value.imageBase64,
          result: null,
          error: '',
        }
        actions.syncVisionSessionFromDraft?.()
      } else {
        actions.syncVisionDraftFromSession?.()
      }
      return openModal({
        type: 'image-recognition-debug',
        component: ImageRecognitionDebugModal,
        props: {},
        options: {
          title: '',
          headerComponent: VisionDialogHeader,
          headerProps: { label: '识图调试', onSelect: (key, modalId) => {
            if (key !== 'screenshot') return
            actions.closeModal?.(modalId)
            actions.openScreenshotPreview?.()
          } },
          size: 'full',
          panelClass: 'image-recognition-debug-panel',
          contentClass: 'image-recognition-debug-content',
          destroyOnClose: false,
        },
      })
    },

    openCropModal() {
      return openModal({
        type: 'crop-modal',
        component: CropModal,
        props: {},
        options: {
          title: '截图编辑 (裁切)',
          size: 'xl',
          panelClass: 'crop-modal-panel',
          contentClass: 'crop-modal-content-wrap',
        },
      })
    },
  }
}

