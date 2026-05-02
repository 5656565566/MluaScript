import { ref } from 'vue'

export function createUiState() {
  return {
    loading: ref(false),
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
    taskManagerQuery: ref(''),
    blocklyManagerQuery: ref(''),
    templateEditorModalVisible: ref(false),
    templateEditorModalData: ref(null),
    templateEditorModalCallback: ref(null),
  }
}
