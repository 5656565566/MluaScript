import { ref } from 'vue'

export function createUiState() {
  return {
    loading: ref(false),
    pendingActionCount: ref(0),
    authChecked: ref(false),
    authenticated: ref(false),
    currentUser: ref(''),
    statusText: ref('准备就绪'),
    activeView: ref('blockly'),
    editorLayout: ref('split'),
    showScreenshot: ref(false),
    showScreenshotFullscreen: ref(false),
    screenshotPosition: ref({ x: 0, y: 64 }),
    appTheme: ref('system'),
    sidebarCollapsed: ref(false),
    logOrigin: ref('runtime'),
    autoRefresh: ref(true),
    autoSaveBlockly: ref(true),
    runLogsSelectedDevice: ref('all'),
    runLogsSelectedLevel: ref('all'),
    runLogsAutoScroll: ref(true),
    taskManagerQuery: ref(''),
    taskManagerActiveTab: ref('resource-list'),
    taskManagerResourceQuery: ref(''),
    deviceManagerQuery: ref(''),
    blocklyManagerQuery: ref(''),
    templateEditorModalVisible: ref(false),
    templateEditorModalData: ref(null),
    templateEditorModalCallback: ref(null),
  }
}
