<script setup>
import { computed, defineAsyncComponent, h, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowBackOutline,
  BugOutline,
  CameraOutline,
  CheckmarkCircleOutline,
  CheckmarkOutline,
  CloseOutline,
  CloudUploadOutline,
  CodeSlashOutline,
  CreateOutline,
  CubeOutline,
  DocumentOutline,
  DocumentTextOutline,
  DownloadOutline,
  FolderOutline,
  FolderOpenOutline,
  GridOutline,
  HardwareChipOutline,
  ImageOutline,
  LinkOutline,
  ListOutline,
  PencilOutline,
  PlayOutline,
  RefreshOutline,
  SaveOutline,
  SearchOutline,
  StopCircleOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import {
  NAlert,
  NButton,
  NCollapseTransition,
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NIcon,
  NList,
  NListItem,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
  NTooltip,
  NTree,
} from 'naive-ui'
import { state, actions } from '../store'
import { compileBlocklyXml } from '../blockly'
import { projectApi } from '../api/projectApi'

const BlocklyEditorPane = defineAsyncComponent(() => import('./editor/BlocklyEditorPane.vue'))
const LuaPreviewDrawer = defineAsyncComponent(() => import('./editor/LuaPreviewDrawer.vue'))
const TextCodeEditor = defineAsyncComponent(() => import('./editor/TextCodeEditor.vue'))

const createVisible = ref(false)
const editVisible = ref(false)
const editBusy = ref(false)
const buildVisible = ref(false)
const createError = ref('')
const editError = ref('')
const operationVisible = ref(false)
const operationMode = ref('file')
const operationPath = ref('')
const operationError = ref('')
const pendingUploadFile = ref(null)
const uploadInputRef = ref(null)
const unsavedVisible = ref(false)
const deleteVisible = ref(false)
const deleteTargetPath = ref('')
const deleteError = ref('')
const deleteBusy = ref(false)
const unsavedBusy = ref(false)
const pendingNavigation = ref(null)
const projectEditorShellRef = ref(null)
const blocklyEditorPaneRef = ref(null)
const projectTreeVisible = state.projectTreeVisible
const projectTreeWidth = state.projectTreeWidth
const projectTreeContextVisible = ref(false)
const projectTreeContextX = ref(0)
const projectTreeContextY = ref(0)
const projectTreeContextNode = ref(null)
const uploadBaseDirectory = ref('')
const renameSourcePath = ref('')
const operationDirectory = ref('')
const projectTreeDragNode = ref(null)
const expandedProjectKey = ref(null)
const projectQuery = ref('')

const FILE_AUTOSAVE_DELAY = 600
const PROJECT_TREE_MIN_WIDTH = 200
const PROJECT_TREE_MAX_WIDTH = 420
const PROJECT_TREE_RESIZE_STEP = 16
let stopProjectTreeResize = null
const fileAutosaveTimers = new Map()

const createForm = ref({
  name: '',
  packageId: '',
  version: '0.1.0',
  author: '',
  description: '',
  directory: '',
  template: 'lua-package',
})

const editForm = ref({
  name: '',
  packageId: '',
  version: '',
  author: '',
  description: '',
})

const templateOptions = [
  { label: 'Lua 可打包项目', value: 'lua-package' },
  { label: 'Blockly 可打包项目', value: 'blockly-package' },
  { label: 'Maa 自动化项目', value: 'maa' },
  { label: 'Blockly 单文件', value: 'blockly-file' },
  { label: 'Lua 单文件', value: 'lua-file' },
]

const isPackageTemplate = computed(() => ['lua-package', 'blockly-package', 'maa'].includes(createForm.value.template))
const hasWorkspaceItems = computed(() => Boolean(state.projects.value.length))
const filteredProjects = computed(() => {
  const query = projectQuery.value.trim().toLowerCase()
  if (!query) return state.projects.value
  return state.projects.value.filter((project) => [
    project.name,
    project.description,
    project.directory,
    project.package_id,
    projectTypeLabel(project.project_type),
  ].some(value => String(value || '').toLowerCase().includes(query)))
})

const currentProject = computed(() => state.currentProject.value)
const selectedFile = computed(() => state.projectFile.value)
const selectedFileIsText = computed(() => selectedFile.value?.encoding === 'utf-8')
const selectedFileIsImage = computed(() => editorKindForFile(selectedFile.value) === 'image')
const selectedFilePreviewUrl = computed(() => (
  selectedFileIsImage.value && selectedFile.value?.path
    ? actions.projectFileDownloadUrl(selectedFile.value.path)
    : ''
))
const imageFilePattern = /\.(png|jpe?g|gif|webp|bmp|svg|avif|ico)$/i
const selectedTreeKeys = computed(() => state.projectSelectedPath.value ? [state.projectSelectedPath.value] : [])
const openFiles = computed(() => state.projectOpenFiles.value)
const selectedDeviceSession = computed(() => (
  state.sessions.value.find(session => session.label === state.selectedSession.value) || null
))
const currentDebugTask = computed(() => state.projectDebugTaskByKey.value[currentProject.value?.key] || null)
const currentDebugTaskView = computed(() => (
  state.tasks.value.find(task => task.task_id === currentDebugTask.value?.taskId) || null
))

const blocklyDocumentPaths = computed(() => {
  const paths = new Set()
  const entrypoints = state.currentManifest.value?.entrypoints || {}
  for (const entrypoint of Object.values(entrypoints)) {
    if (entrypoint?.blockly) paths.add(String(entrypoint.blockly).replaceAll('\\', '/'))
  }
  return paths
})

function editorKindForFile(file) {
  const path = String(file?.path || '').replaceAll('\\', '/')
  if (!path) return 'empty'
  if (file?.encoding !== 'utf-8') {
    return /\.(png|jpe?g|gif|webp|bmp|svg|avif|ico)$/i.test(path) ? 'image' : 'binary'
  }
  if (
    blocklyDocumentPaths.value.has(path)
    || (state.currentProject.value?.project_type === 'blockly-file' && path === state.currentProject.value?.primary_path)
    || (path.startsWith('blockly/') && path.toLowerCase().endsWith('.xml'))
    || /^\s*<xml(?:\s|>)/i.test(String(file?.content || ''))
  ) {
    return 'blockly'
  }
  return 'text'
}

const selectedEditorKind = computed(() => editorKindForFile(selectedFile.value))

const editorKindLabel = computed(() => ({
  blockly: 'Blockly',
  text: '文本',
  image: '图片',
  binary: '二进制',
  empty: '',
}[selectedEditorKind.value]))

function editorMenuIcon(component, visible = true) {
  return () => h(NIcon, { class: 'editor-command-menu-icon' }, {
    default: () => visible ? h(component) : null,
  })
}

function editorMenuLabel(label, shortcut = '') {
  return () => h('span', { class: 'editor-command-menu-label' }, [
    h('span', label),
    shortcut ? h('span', { class: 'editor-command-menu-shortcut' }, shortcut) : null,
  ])
}

function fileMenuProps() {
  return { class: 'editor-command-dropdown editor-file-dropdown' }
}

const fileMenuOptions = computed(() => [
  {
    label: editorMenuLabel('保存', 'Ctrl+S'),
    key: 'save',
    icon: editorMenuIcon(SaveOutline),
    disabled: !selectedFileIsText.value,
  },
  {
    label: editorMenuLabel('下载当前文件'),
    key: 'download',
    icon: editorMenuIcon(DownloadOutline),
    disabled: !selectedFile.value,
  },
  { type: 'divider', key: 'save-divider' },
  {
    label: editorMenuLabel('自动保存'),
    key: 'toggle-auto-save',
    icon: editorMenuIcon(CheckmarkOutline, state.autoSaveFiles.value),
  },
])

const isSingleFileProject = computed(() => ['blockly-file', 'lua-file'].includes(currentProject.value?.project_type))
const buildCommandLabel = computed(() => isSingleFileProject.value ? '导出 Lua' : '打包项目')

const projectMenuOptions = computed(() => [
  {
    label: editorMenuLabel('编辑信息'),
    key: 'edit-info',
    icon: editorMenuIcon(CreateOutline),
    disabled: isSingleFileProject.value,
  },
  { type: 'divider', key: 'info-divider' },
  {
    label: editorMenuLabel('刷新项目'),
    key: 'refresh',
    icon: editorMenuIcon(RefreshOutline),
    disabled: state.projectLoading.value,
  },
  {
    label: editorMenuLabel('校验项目'),
    key: 'validate',
    icon: editorMenuIcon(CheckmarkCircleOutline),
  },
  {
    label: editorMenuLabel(buildCommandLabel.value),
    key: 'build',
    icon: editorMenuIcon(CubeOutline),
    disabled: state.projectBuildLoading.value,
  },
  { type: 'divider', key: 'project-divider' },
  {
    label: editorMenuLabel('返回项目列表'),
    key: 'close-project',
    icon: editorMenuIcon(ArrowBackOutline),
  },
])

function projectMenuProps() {
  return { class: 'editor-command-dropdown editor-project-dropdown' }
}

const debugMenuOptions = computed(() => [
  {
    label: editorMenuLabel('调试项目入口'),
    key: 'debug-entry',
    icon: editorMenuIcon(PlayOutline),
    disabled: state.projectDebugLoading.value,
  },
  {
    label: editorMenuLabel('调试当前文件'),
    key: 'debug-current',
    icon: editorMenuIcon(BugOutline),
    disabled: state.projectDebugLoading.value || !selectedFileIsText.value,
  },
  {
    label: editorMenuLabel('模板调试…'),
    key: 'debug-template',
    icon: editorMenuIcon(CodeSlashOutline),
    disabled: state.projectDebugLoading.value
      || !selectedFileIsText.value
      || !['lua', 'xml'].includes(String(selectedFile.value?.path || '').split('.').pop()?.toLowerCase() || '')
      || !['lua-file', 'lua-package', 'blockly-file', 'blockly-package'].includes(currentProject.value?.project_type || ''),
  },
  {
    label: editorMenuLabel('识图调试…'),
    key: 'debug-image-recognition',
    icon: editorMenuIcon(ImageOutline),
    disabled: !currentProject.value,
  },
  { type: 'divider', key: 'debug-divider' },
  {
    label: editorMenuLabel('查看调试任务'),
    key: 'view-debug-task',
    icon: editorMenuIcon(ListOutline),
    disabled: !currentDebugTask.value,
  },
  {
    label: editorMenuLabel('终止调试任务'),
    key: 'stop-debug-task',
    icon: editorMenuIcon(StopCircleOutline),
    disabled: !currentDebugTask.value || !['pending', 'running'].includes(currentDebugTaskView.value?.status),
  },
])

function debugMenuProps() {
  return { class: 'editor-command-dropdown editor-debug-dropdown' }
}

const deviceMenuOptions = computed(() => [
  {
    label: editorMenuLabel('连接设备…'),
    key: 'connect-device',
    icon: editorMenuIcon(LinkOutline),
  },
  {
    label: editorMenuLabel('选择设备…'),
    key: 'select-device',
    icon: editorMenuIcon(HardwareChipOutline),
  },
  { type: 'divider', key: 'device-divider' },
  {
    label: editorMenuLabel('设备截图'),
    key: 'capture-device',
    icon: editorMenuIcon(CameraOutline),
    disabled: !selectedDeviceSession.value?.canScreencap || state.loading.value,
  },
])

function deviceMenuProps() {
  return { class: 'editor-command-dropdown editor-device-dropdown' }
}

const toolsMenuOptions = computed(() => [
  {
    label: editorMenuLabel('截图预览'),
    key: 'screenshot-preview',
    icon: editorMenuIcon(ImageOutline),
  },
])

function toolsMenuProps() {
  return { class: 'editor-command-dropdown editor-tools-dropdown' }
}

const viewMenuOptions = computed(() => [
  {
    label: editorMenuLabel(projectTreeVisible.value ? '收起项目树' : '展开项目树'),
    key: 'toggle-tree',
    icon: editorMenuIcon(FolderOpenOutline),
  },
  {
    label: editorMenuLabel('Lua 预览'),
    key: 'lua-preview',
    icon: editorMenuIcon(CodeSlashOutline),
    disabled: selectedEditorKind.value !== 'blockly',
  },
])

function viewMenuProps() {
  return { class: 'editor-command-dropdown editor-view-dropdown' }
}

const manifestOwnedPaths = computed(() => {
  const referenced = ['mluascript.yaml']
  const manifest = state.currentManifest.value || {}
  for (const entrypoint of Object.values(manifest.entrypoints || {})) {
    referenced.push(entrypoint?.script, entrypoint?.blockly, entrypoint?.maa, entrypoint?.template)
    referenced.push(...Object.values(entrypoint?.models || {}))
  }
  referenced.push(...Object.values(manifest.resources || {}))
  for (const model of Object.values(manifest.models || {})) referenced.push(model?.path)

  const protectedPaths = new Set()
  for (const rawPath of referenced.filter(Boolean)) {
    const parts = String(rawPath).replaceAll('\\', '/').split('/').filter(Boolean)
    for (let index = 1; index <= parts.length; index += 1) {
      protectedPaths.add(parts.slice(0, index).join('/'))
    }
  }
  return protectedPaths
})

const projectTreeContextOptions = computed(() => {
  const directory = contextDirectory(projectTreeContextNode.value)
  const options = []
  const canCreateLua = ['lua-package', 'blockly-package'].includes(currentProject.value?.project_type)
    && (directory === 'scripts' || directory.startsWith('scripts/'))
  const canCreateBlockly = currentProject.value?.project_type === 'blockly-package'
    && (directory === 'blockly' || directory.startsWith('blockly/'))

  // 快捷源文件入口只出现在对应的受控源目录，避免菜单暗中跳转到其他位置。
  if (canCreateLua) {
    options.push({ label: '新建 Lua 文件…', key: 'new-lua-file', icon: editorMenuIcon(DocumentTextOutline) })
  }
  if (canCreateBlockly) {
    options.push({ label: '新建 Blockly 文件…', key: 'new-blockly-file', icon: editorMenuIcon(GridOutline) })
  }
  const contextPath = String(projectTreeContextNode.value?.key || '')
  const contextIsImage = projectTreeContextNode.value?.kind === 'file' && imageFilePattern.test(contextPath)
  if (contextIsImage) {
    options.push(
      { label: '在截图工具中打开', key: 'open-screenshot-tool', icon: editorMenuIcon(CameraOutline) },
      { label: '发送到识图调试', key: 'open-image-recognition', icon: editorMenuIcon(ImageOutline) },
      { label: '作为识图模板', key: 'use-image-template', icon: editorMenuIcon(GridOutline) },
      { type: 'divider', key: 'image-tools-divider' },
    )
  }
  options.push(
    { label: '新建其他文件…', key: 'new-file', icon: editorMenuIcon(DocumentOutline), disabled: isSingleFileProject.value },
    { label: '新建目录…', key: 'new-directory', icon: editorMenuIcon(FolderOutline), disabled: isSingleFileProject.value },
    { label: '上传文件…', key: 'upload', icon: editorMenuIcon(CloudUploadOutline), disabled: isSingleFileProject.value },
    { type: 'divider', key: 'tree-edit-divider' },
    {
      label: '重命名',
      key: 'rename',
      icon: editorMenuIcon(PencilOutline),
      disabled: isSingleFileProject.value
        || !projectTreeContextNode.value
        || String(projectTreeContextNode.value.key || '') === 'mluascript.yaml'
        || (
          projectTreeContextNode.value.kind === 'directory'
          && manifestOwnedPaths.value.has(String(projectTreeContextNode.value.key || ''))
      ),
    },
    {
      label: '删除文件',
      key: 'delete-file',
      icon: editorMenuIcon(TrashOutline),
      disabled: isSingleFileProject.value
        || projectTreeContextNode.value?.kind !== 'file'
        || manifestOwnedPaths.value.has(String(projectTreeContextNode.value?.key || '')),
    },
  )
  return options
})

function projectTreeMenuProps() {
  return { class: 'editor-command-dropdown editor-project-tree-dropdown' }
}

const projectTreeData = computed(() => {
  const roots = []
  const nodeByPath = new Map()
  const items = [...state.projectTree.value].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === 'directory' ? -1 : 1
    return left.path.localeCompare(right.path)
  })

  for (const item of items) {
    const parts = String(item.path).split('/').filter(Boolean)
    let parentChildren = roots
    let currentPath = ''
    for (let index = 0; index < parts.length; index += 1) {
      currentPath = currentPath ? `${currentPath}/${parts[index]}` : parts[index]
      let node = nodeByPath.get(currentPath)
      if (!node) {
        const isItem = index === parts.length - 1
        const kind = isItem ? item.kind : 'directory'
        node = {
          key: currentPath,
          label: parts[index],
          kind,
          isLeaf: kind === 'file',
          item: isItem ? item : null,
          children: kind === 'directory' ? [] : undefined,
        }
        nodeByPath.set(currentPath, node)
        parentChildren.push(node)
      } else if (index === parts.length - 1) {
        node.kind = item.kind
        node.isLeaf = item.kind === 'file'
        node.item = item
      }
      if (node.kind === 'directory') parentChildren = node.children
    }
  }
  return roots
})

function formatSize(size) {
  const value = Number(size || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function documentLabel(tab) {
  const filename = String(tab?.path || '').split('/').pop() || ''
  return editorKindForFile(tab?.file) === 'blockly' ? filename.replace(/\.xml$/i, '') : filename
}

function projectTypeLabel(projectType) {
  return ({
    'lua-package': 'Lua 可打包项目',
    'blockly-package': 'Blockly 可打包项目',
    maa: 'Maa 自动化项目',
    'blockly-file': 'Blockly 单文件',
    'lua-file': 'Lua 单文件',
  })[projectType] || projectType
}

function isPackageProject(project) {
  return ['lua-package', 'blockly-package', 'maa'].includes(project?.project_type)
}

function projectTypeClass(projectType) {
  if (String(projectType).startsWith('lua')) return 'project-type-lua'
  if (String(projectType).startsWith('blockly')) return 'project-type-blockly'
  return 'project-type-maa'
}

function toggleProjectDetails(project) {
  expandedProjectKey.value = expandedProjectKey.value === project.key ? null : project.key
}

function contextDirectory(node) {
  const path = String(node?.key || '')
  if (!path) return ''
  if (node.kind === 'directory') return path
  return path.split('/').slice(0, -1).join('/')
}

function parentDirectory(node) {
  return String(node?.key || '').split('/').slice(0, -1).join('/')
}

function joinProjectPath(directory, filename) {
  return directory ? `${directory}/${filename}` : filename
}

function ensureFileSuffix(filename, suffix) {
  const value = String(filename || '').trim()
  return value.toLowerCase().endsWith(suffix) ? value : `${value}${suffix}`
}

function clampProjectTreeWidth(width) {
  return Math.min(PROJECT_TREE_MAX_WIDTH, Math.max(PROJECT_TREE_MIN_WIDTH, Math.round(width)))
}

function toggleProjectTree() {
  projectTreeVisible.value = !projectTreeVisible.value
}

function setProjectTreeWidth(width) {
  projectTreeWidth.value = clampProjectTreeWidth(width)
  projectEditorShellRef.value?.style.setProperty('--project-tree-width', `${projectTreeWidth.value}px`)
}

function handleProjectTreeResizeKeydown(event) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  const direction = event.key === 'ArrowLeft' ? -1 : 1
  setProjectTreeWidth(projectTreeWidth.value + direction * PROJECT_TREE_RESIZE_STEP)
}

function startProjectTreeResize(event) {
  if (event.button !== 0 || !projectTreeVisible.value) return
  event.preventDefault()
  stopProjectTreeResize?.()

  const shell = projectEditorShellRef.value
  const treePanel = shell?.querySelector('.project-tree-panel')
  if (!shell || !treePanel) return

  const startX = event.clientX
  const startWidth = treePanel.getBoundingClientRect().width
  let nextWidth = clampProjectTreeWidth(startWidth)

  const handlePointerMove = (moveEvent) => {
    nextWidth = clampProjectTreeWidth(startWidth + moveEvent.clientX - startX)
    shell.style.setProperty('--project-tree-width', `${nextWidth}px`)
  }
  const finishResize = () => {
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', finishResize)
    window.removeEventListener('pointercancel', finishResize)
    shell.classList.remove('is-resizing')
    projectTreeWidth.value = nextWidth
    stopProjectTreeResize = null
  }

  shell.classList.add('is-resizing')
  window.addEventListener('pointermove', handlePointerMove)
  window.addEventListener('pointerup', finishResize)
  window.addEventListener('pointercancel', finishResize)
  stopProjectTreeResize = finishResize
}

async function refreshWorkspace() {
  try {
    if (currentProject.value) await actions.reloadProjectTree()
    else await actions.loadProjects()
  } catch (error) {
    actions.setStatus(error?.message || '刷新项目失败', 'error')
  }
}

async function openProject(project) {
  try {
    await actions.openProject(project.key)
  } catch (error) {
    actions.setStatus(error?.message || '打开项目失败', 'error')
  }
}

function startCreate() {
  createError.value = ''
  createForm.value = {
    name: '',
    packageId: '',
    version: '0.1.0',
    author: '',
    description: '',
    directory: '',
    template: 'lua-package',
  }
  createVisible.value = true
}

async function submitCreate() {
  const payload = { ...createForm.value }
  if (!payload.name.trim()) {
    createError.value = '名称不能为空'
    return
  }
  if (isPackageTemplate.value && (!payload.packageId.trim() || !payload.version.trim())) {
    createError.value = '项目名称、包 ID 和版本不能为空'
    return
  }
  try {
    await actions.createProject(payload)
    createVisible.value = false
  } catch (error) {
    createError.value = error?.message || '创建项目失败'
  }
}

function startEditProjectInfo() {
  if (!currentProject.value) return
  editError.value = ''
  editForm.value = {
    name: currentProject.value.name || '',
    packageId: currentProject.value.package_id || '',
    version: currentProject.value.version || '',
    author: currentProject.value.author || '',
    description: currentProject.value.description || '',
  }
  editVisible.value = true
}

async function submitEditProjectInfo() {
  const payload = { ...editForm.value }
  if (!payload.name.trim() || !payload.packageId.trim() || !payload.version.trim()) {
    editError.value = '项目名称、包 ID 和版本不能为空'
    return
  }
  editBusy.value = true
  editError.value = ''
  try {
    await actions.updateProjectInfo(payload)
    editVisible.value = false
  } catch (error) {
    editError.value = error?.message || '更新项目信息失败'
  } finally {
    editBusy.value = false
  }
}

async function runNavigation(navigation) {
  try {
    await navigation?.()
  } catch (error) {
    actions.setStatus(error?.message || '切换项目文件失败', 'error')
  }
}

async function guardDirtyDocument(navigation) {
  if (!state.projectFileDirty.value) {
    await runNavigation(navigation)
    return
  }
  pendingNavigation.value = navigation
  unsavedVisible.value = true
}

async function handleTreeSelection(keys, _options, meta) {
  const node = meta?.node
  if (!node || node.kind !== 'file' || !node.item) return
  if (node.item.path === state.projectSelectedPath.value) return
  await runNavigation(() => actions.selectProjectFile(node.item))
}

async function activateDocumentTab(tab) {
  if (!tab || tab.path === state.projectSelectedPath.value) return
  await runNavigation(() => actions.selectProjectFile({ kind: 'file', path: tab.path }))
}

async function closeDocumentTab(tab, event) {
  event?.stopPropagation()
  if (!tab) return
  if (tab.path !== state.projectSelectedPath.value) {
    await actions.selectProjectFile({ kind: 'file', path: tab.path })
  }
  await guardDirtyDocument(() => actions.closeProjectFile(tab.path))
}

async function resolveUnsaved(mode) {
  if (mode === 'cancel') {
    unsavedVisible.value = false
    pendingNavigation.value = null
    return
  }
  unsavedBusy.value = true
  try {
    if (mode === 'save') await actions.saveProjectFile()
    if (mode === 'discard') actions.discardProjectFileChanges()
    const navigation = pendingNavigation.value
    unsavedVisible.value = false
    pendingNavigation.value = null
    await runNavigation(navigation)
  } catch (error) {
    actions.setStatus(error?.message || '保存项目文件失败', 'error')
  } finally {
    unsavedBusy.value = false
  }
}

async function closeProject() {
  const dirtyTab = state.projectOpenFiles.value.find(tab => tab.dirty)
  if (!dirtyTab) {
    actions.closeProject()
    return
  }
  if (dirtyTab.path !== state.projectSelectedPath.value) {
    await actions.selectProjectFile({ kind: 'file', path: dirtyTab.path })
  }
  await guardDirtyDocument(closeProject)
}

async function saveFile() {
  clearFileAutosave(state.projectSelectedPath.value)
  try {
    await actions.saveProjectFile()
  } catch (error) {
    actions.setStatus(error?.message || '保存项目文件失败', 'error')
  }
}

function setFileContent(content) {
  actions.setProjectFileContent(content)
  scheduleFileAutosave(state.projectSelectedPath.value)
}

function handleBlocklyGenerated(code, diagnostics, stale) {
  actions.setProjectGeneratedLua(code, diagnostics, stale)
}

function clearFileAutosave(path) {
  const timer = fileAutosaveTimers.get(path)
  if (timer) window.clearTimeout(timer)
  fileAutosaveTimers.delete(path)
}

function clearAllFileAutosaves() {
  for (const timer of fileAutosaveTimers.values()) window.clearTimeout(timer)
  fileAutosaveTimers.clear()
}

function clearFileAutosavesUnder(path) {
  for (const timerPath of [...fileAutosaveTimers.keys()]) {
    if (timerPath === path || timerPath.startsWith(`${path}/`)) clearFileAutosave(timerPath)
  }
}

function scheduleFileAutosave(path) {
  const tab = state.projectOpenFiles.value.find(item => item.path === path)
  if (!state.autoSaveFiles.value || !path || tab?.file?.encoding !== 'utf-8') return
  clearFileAutosave(path)
  const timer = window.setTimeout(() => {
    fileAutosaveTimers.delete(path)
    actions.saveProjectFile({ path, notify: false }).catch((error) => {
      actions.setStatus(error?.message || '自动保存文件失败', 'error')
    })
  }, FILE_AUTOSAVE_DELAY)
  fileAutosaveTimers.set(path, timer)
}

function scheduleDirtyFileAutosaves() {
  for (const tab of state.projectOpenFiles.value) {
    if (tab.dirty) scheduleFileAutosave(tab.path)
  }
}

function setAutoSaveFiles(enabled) {
  state.autoSaveFiles.value = Boolean(enabled)
  if (!state.autoSaveFiles.value) clearAllFileAutosaves()
}

function startFileOperation(mode, baseDirectory = '') {
  operationMode.value = mode
  operationDirectory.value = baseDirectory
  operationError.value = ''
  pendingUploadFile.value = null
  operationPath.value = mode === 'directory'
    ? 'new-folder'
    : mode === 'blockly-file'
      ? 'new.xml'
      : mode === 'lua-file'
        ? 'new.lua'
        : 'new.txt'
  operationVisible.value = true
}

function startRename(node) {
  if (!node) return
  operationMode.value = 'rename'
  operationError.value = ''
  renameSourcePath.value = String(node.key || '')
  operationDirectory.value = parentDirectory(node)
  operationPath.value = String(node.label || '')
  operationVisible.value = true
}

function startDeleteFile(node) {
  if (!node || node.kind !== 'file') return
  deleteTargetPath.value = String(node.key || '')
  deleteError.value = ''
  deleteVisible.value = true
}

async function confirmDeleteFile() {
  if (!deleteTargetPath.value || deleteBusy.value) return
  deleteBusy.value = true
  deleteError.value = ''
  try {
    await actions.deleteProjectFile(deleteTargetPath.value)
    deleteVisible.value = false
    deleteTargetPath.value = ''
  } catch (error) {
    deleteError.value = error?.message || '删除文件失败'
  } finally {
    deleteBusy.value = false
  }
}

function chooseUpload(baseDirectory = '') {
  uploadBaseDirectory.value = baseDirectory
  uploadInputRef.value?.click()
}

function handleUploadChosen(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  pendingUploadFile.value = file
  operationMode.value = 'upload'
  operationPath.value = joinProjectPath(uploadBaseDirectory.value, file.name)
  operationError.value = ''
  operationVisible.value = true
}

function showProjectTreeContextMenu(event, node = null) {
  event.preventDefault()
  event.stopPropagation()
  projectTreeContextVisible.value = false
  projectTreeContextNode.value = node
  projectTreeContextX.value = event.clientX
  projectTreeContextY.value = event.clientY
  nextTick(() => {
    projectTreeContextVisible.value = true
  })
}

function projectTreeNodeProps({ option }) {
  return {
    onContextmenu: event => showProjectTreeContextMenu(event, option),
  }
}

function handleProjectTreeContextSelect(key) {
  projectTreeContextVisible.value = false
  const directory = contextDirectory(projectTreeContextNode.value)
  if (key === 'new-lua-file' && (directory === 'scripts' || directory.startsWith('scripts/'))) {
    startFileOperation('lua-file', directory)
  }
  else if (key === 'new-blockly-file' && (directory === 'blockly' || directory.startsWith('blockly/'))) {
    startFileOperation('blockly-file', directory)
  }
  else if (key === 'new-file') startFileOperation('file', directory)
  else if (key === 'new-directory') startFileOperation('directory', directory)
  else if (key === 'upload') chooseUpload(directory)
  else if (key === 'open-screenshot-tool') void actions.openProjectImageInScreenshot(String(projectTreeContextNode.value?.key || ''))
  else if (key === 'open-image-recognition') actions.openProjectImageRecognition(String(projectTreeContextNode.value?.key || ''))
  else if (key === 'use-image-template') actions.openProjectImageRecognition(String(projectTreeContextNode.value?.key || ''), { asTemplate: true })
  else if (key === 'rename') startRename(projectTreeContextNode.value)
  else if (key === 'delete-file') startDeleteFile(projectTreeContextNode.value)
}

function allowProjectTreeDrop({ dropPosition, node }) {
  if (isSingleFileProject.value) return false
  if (dropPosition === 'inside' && node?.kind !== 'directory') return false
  const sourcePath = String(projectTreeDragNode.value?.key || '')
  if (!sourcePath || manifestOwnedPaths.value.has(sourcePath)) return false
  const targetDirectory = dropPosition === 'inside' ? String(node?.key || '') : parentDirectory(node)
  if (targetDirectory === sourcePath || targetDirectory.startsWith(`${sourcePath}/`)) return false
  const destinationPath = joinProjectPath(targetDirectory, sourcePath.split('/').pop() || '')
  return !state.projectTree.value.some(item => item.path === destinationPath && item.path !== sourcePath)
}

function handleProjectTreeDragStart({ event, node }) {
  const sourcePath = String(node?.key || '')
  if (!sourcePath || isSingleFileProject.value || manifestOwnedPaths.value.has(sourcePath)) {
    event.preventDefault()
    projectTreeDragNode.value = null
    return
  }
  projectTreeDragNode.value = node
}

function handleProjectTreeDragEnd() {
  projectTreeDragNode.value = null
}

async function moveDroppedProjectNode(dragNode, targetDirectory) {
  const sourcePath = String(dragNode?.key || '')
  if (!sourcePath || manifestOwnedPaths.value.has(sourcePath)) return
  const filename = sourcePath.split('/').pop() || ''
  const destinationPath = joinProjectPath(targetDirectory, filename)
  if (!filename || destinationPath === sourcePath) return

  clearFileAutosavesUnder(sourcePath)
  try {
    await actions.moveProjectPath(sourcePath, destinationPath)
    scheduleDirtyFileAutosaves()
  } catch (error) {
    scheduleDirtyFileAutosaves()
    actions.setStatus(error?.message || '移动项目文件失败', 'error')
  } finally {
    projectTreeDragNode.value = null
  }
}

function handleProjectTreeDrop({ event, node, dragNode, dropPosition }) {
  event.stopPropagation()
  const targetDirectory = dropPosition === 'inside' ? String(node.key || '') : parentDirectory(node)
  void moveDroppedProjectNode(dragNode, targetDirectory)
}

function handleProjectTreeRootDrop(event) {
  event.preventDefault()
  void moveDroppedProjectNode(projectTreeDragNode.value, '')
}

function handleFileMenuSelect(key) {
  if (key === 'save') void saveFile()
  else if (key === 'download') downloadSelectedFile()
  else if (key === 'toggle-auto-save') setAutoSaveFiles(!state.autoSaveFiles.value)
}

function handleProjectMenuSelect(key) {
  if (key === 'edit-info') startEditProjectInfo()
  else if (key === 'refresh') void refreshWorkspace()
  else if (key === 'validate') void validateProject()
  else if (key === 'build') void buildProject()
  else if (key === 'close-project') void closeProject()
}

async function startProjectDebug(entryPath = '') {
  try {
    const task = await actions.debugProject({ entryPath })
    if (task?.taskId) await openTaskById(task.taskId)
  } catch (error) {
    actions.setStatus(error?.message || '启动项目调试失败', 'error')
  }
}

async function startProjectTemplateDebug() {
  const entryPath = selectedFile.value?.path || ''
  if (!entryPath) return
  try {
    await actions.saveAllProjectFiles()
    const snapshot = await actions.buildProjectDebugSnapshot(entryPath)
    await actions.loadProjectTemplate(currentProject.value.key, entryPath, snapshot)
    state.activeView.value = 'template-runner'
  } catch (error) {
    actions.setStatus(error?.message || '加载模板调试失败', 'error')
  }
}

async function viewProjectDebugTask() {
  const taskId = currentDebugTask.value?.taskId
  if (!taskId) return
  await openTaskById(taskId)
}

async function openTaskById(taskId) {
  state.selectedTaskId.value = taskId
  state.taskManagerActiveTab.value = 'task-status'
  state.activeView.value = 'task-manager'
  try {
    await actions.fetchTaskDetail(taskId)
  } catch (error) {
    actions.setStatus(error?.message || '加载调试任务失败', 'error')
  }
}

async function stopProjectDebugTask() {
  const task = currentDebugTask.value
  if (!task?.taskId) return
  try {
    await actions.stopTask(task.taskId, task.kind || 'script')
    actions.setStatus(`已终止调试任务: ${task.taskId}`, 'success')
  } catch (error) {
    actions.setStatus(error?.message || '终止调试任务失败', 'error')
  }
}

function handleDebugMenuSelect(key) {
  if (key === 'debug-entry') void startProjectDebug(currentProject.value?.primary_path || '')
  else if (key === 'debug-current') void startProjectDebug(selectedFile.value?.path || '')
  else if (key === 'debug-template') void startProjectTemplateDebug()
  else if (key === 'debug-image-recognition') actions.openImageRecognitionDebugModal()
  else if (key === 'view-debug-task') void viewProjectDebugTask()
  else if (key === 'stop-debug-task') void stopProjectDebugTask()
}

function handleDeviceMenuSelect(key) {
  if (key === 'connect-device') state.activeView.value = 'device'
  else if (key === 'select-device') state.activeView.value = 'device-manager'
  else if (key === 'capture-device') void actions.handleAction(actions.doScreencap).catch(() => null)
}

function handleToolsMenuSelect(key) {
  if (key === 'screenshot-preview') void actions.openScreenshotPreview()
}

function handleViewMenuSelect(key) {
  if (key === 'toggle-tree') toggleProjectTree()
  else if (key === 'lua-preview') state.projectLuaPreviewVisible.value = true
}

async function submitFileOperation() {
  const input = operationPath.value.trim().replaceAll('\\', '/')
  if (!input) {
    operationError.value = '项目内路径不能为空'
    return
  }
  try {
    if (['file', 'lua-file', 'blockly-file'].includes(operationMode.value)) {
      const filename = operationMode.value === 'lua-file'
        ? ensureFileSuffix(input, '.lua')
        : operationMode.value === 'blockly-file'
          ? ensureFileSuffix(input, '.xml')
          : input
      const path = joinProjectPath(operationDirectory.value, filename)
      const content = operationMode.value === 'lua-file'
        ? '-- MluaScript Lua script\n\n'
        : operationMode.value === 'blockly-file'
          ? '<xml xmlns="https://developers.google.com/blockly/xml"></xml>\n'
          : ''
      const data = await actions.createProjectFile(path, content)
      operationVisible.value = false
      await actions.selectProjectFile({ kind: 'file', path: data.path })
    } else if (operationMode.value === 'directory') {
      const path = joinProjectPath(operationDirectory.value, input)
      await actions.createProjectDirectory(path)
      operationVisible.value = false
    } else if (operationMode.value === 'upload') {
      const path = input
      await actions.uploadProjectFile(path, pendingUploadFile.value)
      operationVisible.value = false
    } else {
      const sourcePath = renameSourcePath.value
      clearFileAutosavesUnder(sourcePath)
      try {
        await actions.renameProjectPath(sourcePath, input)
        operationVisible.value = false
      } finally {
        scheduleDirtyFileAutosaves()
      }
    }
  } catch (error) {
    operationError.value = error?.message || '项目文件操作失败'
  }
}

async function validateProject() {
  try {
    await actions.validateProject()
  } catch (error) {
    actions.setStatus(error?.message || '项目校验失败', 'error')
  }
}

async function buildProject() {
  try {
    const projectType = state.currentProject.value?.project_type || ''
    if (projectType === 'blockly-package') {
      await actions.saveAllProjectFiles()
      const generatedModules = {}
      const blocklyFiles = state.projectTree.value.filter(item =>
        item.kind === 'file' && item.path.startsWith('blockly/') && item.path.toLowerCase().endsWith('.xml')
      )
      for (const item of blocklyFiles) {
        const openTab = state.projectOpenFiles.value.find(tab => tab.path === item.path)
        const content = openTab?.content ?? (await projectApi.readFile(state.currentProject.value.key, item.path)).content ?? ''
        const compiled = compileBlocklyXml(content)
        if (compiled.stale || compiled.diagnostics.length) {
          const message = compiled.diagnostics[0]?.message || 'Lua 生成失败'
          throw new Error(`${item.path}: ${message}`)
        }
        generatedModules[item.path] = compiled.code
      }
      const result = await actions.buildProject({ generatedModules })
      if (result) buildVisible.value = true
      return
    }
    if (selectedEditorKind.value === 'blockly') {
      const compiled = blocklyEditorPaneRef.value?.compile?.()
      if (compiled) actions.setProjectGeneratedLua(compiled.code, compiled.diagnostics, compiled.stale)
    }
    const result = await actions.buildProject()
    if (result) buildVisible.value = true
  } catch (error) {
    actions.setStatus(error?.message || '项目打包失败', 'error')
  }
}

function downloadBuild() {
  const path = state.projectBuildResult.value?.downloadPath
  if (path) window.location.assign(path)
}

function downloadSelectedFile() {
  const path = selectedFile.value?.path
  const url = actions.projectFileDownloadUrl(path)
  if (url) window.location.assign(url)
}

function handleBeforeUnload(event) {
  if (!state.projectOpenFiles.value.some(tab => tab.dirty)) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => {
  refreshWorkspace()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  clearAllFileAutosaves()
  stopProjectTreeResize?.()
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<template>
  <section class="editor-workspace">
    <header class="editor-toolbar">
      <div class="editor-toolbar-start">
        <n-tooltip v-if="currentProject" trigger="hover">
          <template #trigger>
            <n-button
              quaternary
              circle
              size="small"
              :aria-label="projectTreeVisible ? '收起项目树' : '展开项目树'"
              :aria-pressed="projectTreeVisible"
              @click="toggleProjectTree"
            >
              <template #icon>
                <n-icon><folder-open-outline /></n-icon>
              </template>
            </n-button>
          </template>
          {{ projectTreeVisible ? '收起项目树' : '展开项目树' }}
        </n-tooltip>
        <div class="editor-title">
          <n-text strong>{{ currentProject ? currentProject.name : '编辑器' }}</n-text>
          <n-text v-if="currentProject" depth="3" class="editor-subtitle">
            {{ isPackageProject(currentProject) ? `v${currentProject.version}` : currentProject.directory }}
          </n-text>
        </div>
      </div>
      <n-space v-if="!currentProject" size="small">
        <n-button size="small" @click="refreshWorkspace" :loading="state.projectLoading.value">刷新</n-button>
        <n-button size="small" type="primary" @click="startCreate">创建项目</n-button>
      </n-space>
      <nav v-else class="editor-menubar" aria-label="编辑器菜单">
        <n-dropdown trigger="click" :options="fileMenuOptions" :menu-props="fileMenuProps" @select="handleFileMenuSelect">
          <n-button text size="small">文件</n-button>
        </n-dropdown>
        <n-dropdown trigger="click" :options="projectMenuOptions" :menu-props="projectMenuProps" @select="handleProjectMenuSelect">
          <n-button text size="small">项目</n-button>
        </n-dropdown>
          <n-dropdown trigger="click" :options="debugMenuOptions" :menu-props="debugMenuProps" @select="handleDebugMenuSelect">
            <n-button text size="small">调试</n-button>
          </n-dropdown>
          <n-dropdown trigger="click" :options="deviceMenuOptions" :menu-props="deviceMenuProps" @select="handleDeviceMenuSelect">
            <n-button text size="small">设备</n-button>
          </n-dropdown>
          <n-dropdown trigger="click" :options="toolsMenuOptions" :menu-props="toolsMenuProps" @select="handleToolsMenuSelect">
            <n-button text size="small">工具</n-button>
          </n-dropdown>
        <n-dropdown trigger="click" :options="viewMenuOptions" :menu-props="viewMenuProps" @select="handleViewMenuSelect">
          <n-button text size="small">视图</n-button>
        </n-dropdown>
      </nav>
    </header>

    <div v-if="!currentProject" class="project-list-shell">
      <div class="project-list-toolbar">
        <n-input v-model:value="projectQuery" placeholder="搜索项目名称、描述或目录..." clearable>
          <template #prefix>
            <n-icon><SearchOutline /></n-icon>
          </template>
        </n-input>
        <n-text v-if="hasWorkspaceItems" depth="3" class="project-list-count">
          {{ filteredProjects.length }} / {{ state.projects.value.length }} 项
        </n-text>
      </div>
      <n-spin :show="state.projectLoading.value">
        <n-empty v-if="!hasWorkspaceItems" description="还没有项目">
          <template #extra>
            <n-button type="primary" @click="startCreate">创建第一个项目</n-button>
          </template>
        </n-empty>
        <n-empty v-else-if="!filteredProjects.length" description="没有匹配的项目">
          <template #extra>
            <n-button @click="projectQuery = ''">清除搜索</n-button>
          </template>
        </n-empty>
        <n-list v-else class="project-list" :show-divider="false">
          <n-list-item v-for="project in filteredProjects" :key="project.key" class="project-list-card">
            <div class="project-list-row">
              <div class="project-list-main">
                <div class="project-list-heading">
                  <n-text strong class="project-name">{{ project.name }}</n-text>
                  <n-tag
                    size="small"
                    :bordered="false"
                    class="project-type-tag"
                    :class="projectTypeClass(project.project_type)"
                  >
                    {{ projectTypeLabel(project.project_type) }}
                  </n-tag>
                  <n-tag v-if="!project.valid" size="small" type="error">无效</n-tag>
                </div>
                <n-text v-if="project.description && isPackageProject(project)" depth="3" class="project-description">
                  {{ project.description }}
                </n-text>
                <n-text depth="3" class="project-directory">{{ project.directory }}</n-text>
              </div>
              <div class="project-list-actions">
                <n-button
                  v-if="isPackageProject(project)"
                  text
                  size="small"
                  :aria-expanded="expandedProjectKey === project.key"
                  @click="toggleProjectDetails(project)"
                >
                  {{ expandedProjectKey === project.key ? '收起' : '详情' }}
                </n-button>
                <n-button size="small" type="primary" @click="openProject(project)">打开</n-button>
              </div>
            </div>
            <n-collapse-transition :show="isPackageProject(project) && expandedProjectKey === project.key">
              <dl class="project-detail-grid">
                <div><dt>版本</dt><dd>{{ project.version || '未设置' }}</dd></div>
                <div><dt>作者</dt><dd>{{ project.author || '未填写' }}</dd></div>
                <div class="project-detail-directory"><dt>目录</dt><dd>{{ project.directory }}</dd></div>
                <div><dt>文件</dt><dd>{{ project.file_count }} 个</dd></div>
                <div><dt>模型</dt><dd>{{ project.model_count }} 个</dd></div>
              </dl>
            </n-collapse-transition>
            <n-alert v-if="project.diagnostics?.length" type="error" :bordered="false" class="project-list-diagnostic">
              {{ project.diagnostics[0].message }}
            </n-alert>
          </n-list-item>
        </n-list>
      </n-spin>
    </div>

    <div
      v-else
      ref="projectEditorShellRef"
      class="project-editor-shell"
      :class="{ 'tree-hidden': !projectTreeVisible }"
      :style="{ '--project-tree-width': `${projectTreeWidth}px` }"
    >
      <button
        v-show="projectTreeVisible"
        class="project-tree-overlay"
        type="button"
        aria-label="收起项目树"
        @click="toggleProjectTree"
      />
      <aside v-show="projectTreeVisible" class="project-tree-panel">
        <div class="project-panel-heading">
          <div>
            <n-text strong>项目文件</n-text>
            <n-text depth="3" class="tree-count">{{ state.projectTree.value.length }} 项</n-text>
          </div>
        </div>
        <input ref="uploadInputRef" class="hidden-file-input" type="file" @change="handleUploadChosen" />
        <div
          class="project-tree-scroll"
          @contextmenu="showProjectTreeContextMenu($event)"
          @dragover.self.prevent
          @drop.self="handleProjectTreeRootDrop"
        >
          <n-tree
            block-line
            default-expand-all
            expand-on-click
            :draggable="!isSingleFileProject"
            :allow-drop="allowProjectTreeDrop"
            :data="projectTreeData"
            :node-props="projectTreeNodeProps"
            :selected-keys="selectedTreeKeys"
            @dragstart="handleProjectTreeDragStart"
            @dragend="handleProjectTreeDragEnd"
            @drop="handleProjectTreeDrop"
            @update:selected-keys="handleTreeSelection"
          />
        </div>
        <n-dropdown
          trigger="manual"
          placement="bottom-start"
          :show="projectTreeContextVisible"
          :x="projectTreeContextX"
          :y="projectTreeContextY"
          :options="projectTreeContextOptions"
          :menu-props="projectTreeMenuProps"
          @select="handleProjectTreeContextSelect"
          @clickoutside="projectTreeContextVisible = false"
        />
      </aside>

      <div
        v-show="projectTreeVisible"
        class="project-tree-resizer"
        role="separator"
        aria-label="调整项目树宽度"
        aria-orientation="vertical"
        :aria-valuemin="PROJECT_TREE_MIN_WIDTH"
        :aria-valuemax="PROJECT_TREE_MAX_WIDTH"
        :aria-valuenow="projectTreeWidth"
        tabindex="0"
        @pointerdown="startProjectTreeResize"
        @keydown="handleProjectTreeResizeKeydown"
      />

      <main class="project-file-panel">
        <div class="document-tabbar">
          <div class="document-tabs" role="tablist" aria-label="打开的文件">
            <div
              v-for="tab in openFiles"
              :key="tab.path"
              class="document-tab"
              :class="{ active: tab.path === state.projectSelectedPath.value }"
            >
              <button
                class="document-tab-select"
                type="button"
                role="tab"
                :aria-selected="tab.path === state.projectSelectedPath.value"
                :title="tab.path"
                @click="activateDocumentTab(tab)"
              >
                <span class="document-name">{{ documentLabel(tab) }}</span>
                <span v-if="tab.dirty" class="dirty-marker" title="尚未保存">●</span>
              </button>
              <button
                class="document-tab-close"
                type="button"
                :aria-label="`关闭 ${documentLabel(tab)}`"
                :title="`关闭 ${tab.path}`"
                @click="closeDocumentTab(tab, $event)"
              >
                <n-icon size="14"><close-outline /></n-icon>
              </button>
            </div>
          </div>
        </div>

        <div class="document-editor-host">
          <div v-if="selectedEditorKind === 'empty'" class="empty-editor" />
          <blockly-editor-pane
            v-else-if="selectedEditorKind === 'blockly'"
            ref="blocklyEditorPaneRef"
            :key="selectedFile.path"
            :model-value="state.projectFileContent.value"
            @update:model-value="setFileContent"
            @generated="handleBlocklyGenerated"
            @save="saveFile"
          />
          <text-code-editor
            v-else-if="selectedEditorKind === 'text'"
            :key="selectedFile.path"
            :path="selectedFile.path"
            :model-value="state.projectFileContent.value"
            @update:model-value="setFileContent"
            @save="saveFile"
          />
          <div v-else-if="selectedFileIsImage" class="image-file-view">
            <div class="image-preview-toolbar">
              <n-text depth="3">{{ selectedFile.path }} · {{ formatSize(selectedFile.size) }}</n-text>
              <n-space size="small">
                <n-button size="small" @click="actions.openProjectImageInScreenshot(selectedFile.path)">截图工具</n-button>
                <n-button size="small" @click="actions.openProjectImageRecognition(selectedFile.path)">识图调试</n-button>
                <n-button size="small" @click="downloadSelectedFile">下载图片</n-button>
              </n-space>
            </div>
            <div class="image-preview-canvas">
              <img :src="selectedFilePreviewUrl" :alt="selectedFile.path" class="image-preview" />
            </div>
          </div>
          <div v-else class="binary-file-view">
            <n-empty description="二进制文件不在浏览器中读取或编辑">
              <template #extra>
                <n-space vertical align="center">
                  <n-text depth="3">{{ selectedFile.path }} · {{ formatSize(selectedFile.size) }}</n-text>
                  <n-button @click="downloadSelectedFile">下载文件</n-button>
                </n-space>
              </template>
            </n-empty>
          </div>
        </div>

        <footer class="editor-statusbar">
          <span>{{ state.projectFileDirty.value ? '尚未保存' : '已保存' }}</span>
          <span v-if="editorKindLabel">{{ editorKindLabel }}</span>
          <span v-if="state.projectBlocklyDiagnostics.value.length">
            {{ state.projectBlocklyDiagnostics.value.length }} 个 Blockly 诊断
          </span>
          <span class="status-spacer" />
          <span>{{ state.statusText.value }}</span>
        </footer>
      </main>
    </div>
  </section>

  <lua-preview-drawer
    :show="state.projectLuaPreviewVisible.value"
    :code="state.projectGeneratedLua.value"
    :diagnostics="state.projectBlocklyDiagnostics.value"
    :stale="state.projectGeneratedLuaStale.value"
    @update:show="value => state.projectLuaPreviewVisible.value = value"
  />

  <n-modal v-model:show="createVisible" preset="card" title="创建项目" class="editor-dialog">
    <n-form label-placement="top">
      <n-form-item label="类型"><n-select v-model:value="createForm.template" :options="templateOptions" /></n-form-item>
      <n-form-item label="项目名称">
        <n-input v-model:value="createForm.name" placeholder="例如：每日任务" />
      </n-form-item>
      <n-form-item v-if="isPackageTemplate" label="包 ID"><n-input v-model:value="createForm.packageId" placeholder="例如：com.example.daily-task" /></n-form-item>
      <n-form-item v-if="isPackageTemplate" label="版本"><n-input v-model:value="createForm.version" placeholder="0.1.0" /></n-form-item>
      <n-form-item v-if="isPackageTemplate" label="作者"><n-input v-model:value="createForm.author" placeholder="作者或团队名称" /></n-form-item>
      <n-form-item v-if="isPackageTemplate" label="描述"><n-input v-model:value="createForm.description" type="textarea" placeholder="简要说明项目用途" /></n-form-item>
      <n-form-item v-if="isPackageTemplate" label="目录名"><n-input v-model:value="createForm.directory" placeholder="留空则根据项目名称生成" /></n-form-item>
      <n-alert v-if="createError" type="error" :bordered="false">{{ createError }}</n-alert>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="createVisible = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">创建</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal v-model:show="editVisible" preset="card" title="编辑项目信息" class="editor-dialog">
    <n-form label-placement="top">
      <n-form-item label="项目名称"><n-input v-model:value="editForm.name" /></n-form-item>
      <n-form-item label="包 ID"><n-input v-model:value="editForm.packageId" /></n-form-item>
      <n-form-item label="版本"><n-input v-model:value="editForm.version" /></n-form-item>
      <n-form-item label="作者"><n-input v-model:value="editForm.author" /></n-form-item>
      <n-form-item label="描述"><n-input v-model:value="editForm.description" type="textarea" /></n-form-item>
      <n-text depth="3">项目目录：{{ currentProject?.directory }}</n-text>
      <n-alert v-if="editError" type="error" :bordered="false" class="operation-error">{{ editError }}</n-alert>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button :disabled="editBusy" @click="editVisible = false">取消</n-button>
        <n-button type="primary" :loading="editBusy" @click="submitEditProjectInfo">保存</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="operationVisible"
    preset="card"
    :title="operationMode === 'lua-file' ? '新建 Lua 文件' : operationMode === 'blockly-file' ? '新建 Blockly 文件' : operationMode === 'file' ? '新建其他文件' : operationMode === 'directory' ? '创建目录' : operationMode === 'rename' ? '重命名' : '上传项目文件'"
    class="editor-dialog"
  >
    <n-form label-placement="top">
      <n-text v-if="['file', 'lua-file', 'blockly-file', 'directory'].includes(operationMode)" depth="3">
        创建位置：{{ operationDirectory || '项目根目录' }}
      </n-text>
      <n-form-item :label="operationMode === 'rename' ? '新名称' : ['file', 'lua-file', 'blockly-file'].includes(operationMode) ? '文件名' : operationMode === 'directory' ? '目录名' : '项目内路径'">
        <n-input v-model:value="operationPath" :placeholder="operationMode === 'upload' ? '例如：resources/assets/image.png' : '输入名称'" @keyup.enter="submitFileOperation" />
      </n-form-item>
      <n-text v-if="pendingUploadFile" depth="3">本地文件：{{ pendingUploadFile.name }} · {{ formatSize(pendingUploadFile.size) }}</n-text>
      <n-alert v-if="operationError" type="error" :bordered="false" class="operation-error">{{ operationError }}</n-alert>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="operationVisible = false">取消</n-button>
        <n-button type="primary" :loading="state.projectFileOperationLoading.value" @click="submitFileOperation">
          {{ operationMode === 'upload' ? '上传' : operationMode === 'rename' ? '重命名' : '创建' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal v-model:show="deleteVisible" preset="card" title="删除文件" class="editor-dialog" :mask-closable="false">
    <n-space vertical>
      <n-alert type="warning" :bordered="false">
        确定删除 {{ deleteTargetPath }}？此操作无法从项目编辑器中撤销。
      </n-alert>
      <n-alert v-if="deleteError" type="error" :bordered="false">{{ deleteError }}</n-alert>
    </n-space>
    <template #footer>
      <n-space justify="end">
        <n-button :disabled="deleteBusy" @click="deleteVisible = false">取消</n-button>
        <n-button type="error" :loading="deleteBusy" @click="confirmDeleteFile">删除</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal :show="unsavedVisible" preset="card" title="文件尚未保存" class="unsaved-dialog" :mask-closable="false" :close-on-esc="false">
    <n-text>要保存 {{ selectedFile?.path }} 的修改吗？</n-text>
    <template #footer>
      <n-space justify="end">
        <n-button :disabled="unsavedBusy" @click="resolveUnsaved('cancel')">取消</n-button>
        <n-button :disabled="unsavedBusy" @click="resolveUnsaved('discard')">放弃修改</n-button>
        <n-button type="primary" :loading="unsavedBusy" @click="resolveUnsaved('save')">保存并继续</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal v-model:show="buildVisible" preset="card" :title="isSingleFileProject ? 'Lua 导出完成' : '项目打包完成'" class="editor-dialog">
    <n-space vertical>
      <n-text strong>{{ state.projectBuildResult.value?.filename }}</n-text>
      <n-text depth="3">{{ formatSize(state.projectBuildResult.value?.size) }} · {{ state.projectBuildResult.value?.files?.length || 0 }} 个文件</n-text>
      <n-text depth="3" class="build-hash">SHA-256: {{ state.projectBuildResult.value?.sha256 }}</n-text>
    </n-space>
    <template #footer>
      <n-space justify="end">
        <n-button @click="buildVisible = false">关闭</n-button>
        <n-button type="primary" @click="downloadBuild">下载 {{ isSingleFileProject ? '.lua' : '.mlspkg' }}</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.editor-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 10px;
  box-sizing: border-box;
  background: var(--color-background);
}

.editor-toolbar,
.project-panel-heading,
.project-list-row,
.document-tabbar,
.editor-statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.editor-toolbar {
  flex: 0 0 auto;
  min-height: 42px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px 6px 0 0;
  background: var(--color-surface);
}

.editor-toolbar-start {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
}

.editor-menubar {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 18px;
  padding-right: 4px;
}

:global(.editor-command-dropdown) {
  min-width: 210px;
}

:global(.editor-command-dropdown .editor-command-menu-label) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  width: 100%;
}

:global(.editor-command-dropdown .editor-command-menu-shortcut) {
  color: var(--color-text-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

:global(.editor-command-dropdown .editor-command-menu-icon) {
  color: var(--color-text-muted);
}

.editor-title,
.project-list-main {
  min-width: 0;
}

.editor-subtitle,
.tree-count {
  margin-left: 10px;
  font-size: 12px;
}

.project-list-shell {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-top: 0;
  background: var(--color-surface);
}

.project-list-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.project-list-toolbar .n-input {
  flex: 1;
  min-width: 0;
}

.project-list-count {
  flex: none;
  font-size: 12px;
  white-space: nowrap;
}

.project-list {
  background: transparent;
}

.project-list-card {
  margin-bottom: 10px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: transparent;
  transition: background-color 0.2s, border-color 0.2s, box-shadow 0.2s;
}

.project-list-card:last-child {
  margin-bottom: 0;
}

.project-list-card:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-2);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.project-list-main {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.project-list-heading,
.project-list-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-description {
  display: -webkit-box;
  overflow: hidden;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.project-directory {
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.project-type-tag {
  flex: 0 0 auto;
  border: 1px solid currentColor;
  background: transparent;
}

.project-type-lua {
  color: var(--color-primary);
}

.project-type-blockly {
  color: var(--color-accent-text);
}

.project-type-maa {
  color: var(--color-warning);
}

.project-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 24px;
  margin: 12px 0 0;
  padding: 12px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface-2);
}

.project-detail-grid > div {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px;
}

.project-detail-grid dt {
  color: var(--color-text-muted);
}

.project-detail-grid dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--color-text-secondary);
}

.project-detail-directory {
  grid-column: 1 / -1;
}

.project-list-diagnostic,
.operation-error {
  margin-top: 8px;
}

@media (max-width: 640px) {
  .project-list-toolbar {
    align-items: stretch;
    flex-direction: column;
    gap: 8px;
  }

  .project-list-count {
    align-self: flex-end;
  }

  .project-list-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .project-list-actions {
    align-self: flex-end;
  }
}

.standalone-file-list {
  margin-top: 10px;
}

.project-editor-shell {
  position: relative;
  display: grid;
  grid-template-columns: var(--project-tree-width, 240px) 6px minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  border: 1px solid var(--color-border);
  border-top: 0;
  background: var(--color-surface);
}

.project-editor-shell.tree-hidden {
  grid-template-columns: minmax(0, 1fr);
}

.project-tree-panel,
.project-file-panel {
  min-width: 0;
  min-height: 0;
}

.project-tree-panel {
  display: flex;
  flex-direction: column;
  background: var(--color-surface-2);
}

.project-tree-overlay {
  display: none;
}

.project-tree-resizer {
  position: relative;
  min-width: 6px;
  padding: 0;
  border: 0;
  outline: 0;
  background: var(--color-surface-2);
  cursor: col-resize;
  touch-action: none;
}

.project-tree-resizer::after {
  position: absolute;
  inset: 0 2px;
  content: '';
  background: var(--color-border);
  transition: background-color 120ms ease;
}

.project-tree-resizer:hover::after,
.project-tree-resizer:focus-visible::after,
.project-editor-shell.is-resizing .project-tree-resizer::after {
  background: var(--color-accent-text);
}

.project-editor-shell.is-resizing {
  cursor: col-resize;
  user-select: none;
}

.project-panel-heading {
  min-height: 38px;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid var(--color-border);
}

.hidden-file-input {
  display: none;
}

.project-tree-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 6px;
}

.project-file-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.document-tabbar {
  flex: 0 0 38px;
  min-width: 0;
  justify-content: flex-start;
  gap: 0;
  overflow: hidden;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-2);
}

.document-tabs {
  display: flex;
  align-self: stretch;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: thin;
}

.document-tab {
  display: flex;
  align-items: center;
  align-self: stretch;
  flex: 0 1 180px;
  min-width: 108px;
  max-width: 220px;
  border-right: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  background: var(--color-surface-2);
}

.document-tab.active {
  color: var(--color-text-primary);
  background: var(--color-surface);
  box-shadow: inset 0 2px 0 var(--color-accent-text);
}

.document-tab-select,
.document-tab-close {
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
}

.document-tab-select {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 4px 0 12px;
  gap: 7px;
  text-align: left;
}

.document-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.document-tab-close {
  display: grid;
  place-items: center;
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  margin-right: 4px;
  padding: 0;
  border-radius: 4px;
  opacity: 0.55;
}

.document-tab-close:hover,
.document-tab-close:focus-visible {
  background: var(--color-button-hover);
  opacity: 1;
}

.dirty-marker {
  color: var(--color-accent-text);
  font-size: 8px;
}

.document-editor-host {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.document-editor-host > :deep(.n-empty) {
  margin: auto;
}

.empty-editor {
  width: 100%;
  height: 100%;
}

.binary-file-view,
.image-file-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.binary-file-view {
  align-items: center;
  justify-content: center;
}

.image-preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.image-preview-toolbar .n-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-preview-canvas {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px;
  background-color: var(--color-surface-2);
  background-image: linear-gradient(45deg, var(--color-border-light) 25%, transparent 25%),
    linear-gradient(-45deg, var(--color-border-light) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--color-border-light) 75%),
    linear-gradient(-45deg, transparent 75%, var(--color-border-light) 75%);
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  background-size: 16px 16px;
}

.image-preview {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  box-shadow: 0 8px 24px var(--color-shadow);
}

.editor-statusbar {
  flex: 0 0 26px;
  justify-content: flex-start;
  padding: 0 10px;
  border-top: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  background: var(--color-surface-2);
  font-size: 11px;
}

.status-spacer {
  flex: 1;
}

.build-hash {
  overflow-wrap: anywhere;
}

:global(.editor-dialog) {
  width: min(520px, calc(100vw - 32px));
}

:global(.unsaved-dialog) {
  width: min(480px, calc(100vw - 32px));
}

@media (max-width: 680px) {
  .editor-toolbar {
    padding: 8px;
  }

  .editor-subtitle {
    display: none;
  }

  .editor-menubar {
    gap: 12px;
  }

  .project-editor-shell {
    display: block;
    grid-template-columns: 1fr;
  }

  .project-tree-panel {
    position: absolute;
    inset: 0 auto 0 0;
    z-index: 2;
    width: min(var(--project-tree-width, 240px), calc(100% - 44px));
    border-right: 1px solid var(--color-border);
    box-shadow: 8px 0 24px var(--color-shadow);
  }

  .project-tree-overlay {
    position: absolute;
    inset: 0;
    z-index: 1;
    display: block;
    width: 100%;
    padding: 0;
    border: 0;
    background: var(--color-overlay);
  }

  .project-tree-resizer {
    display: none !important;
  }

  .project-file-panel {
    height: 100%;
  }
}
</style>
