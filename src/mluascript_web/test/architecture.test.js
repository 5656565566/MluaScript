import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const srcRoot = fileURLToPath(new URL('../src/', import.meta.url))

function listJavaScriptFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = `${directory}/${entry.name}`
    if (entry.isDirectory()) return listJavaScriptFiles(path)
    return entry.name.endsWith('.js') ? [path] : []
  })
}

test('the root store remains a composition root without component imports', () => {
  const source = readFileSync(`${srcRoot}/store.js`, 'utf8')
  assert.equal(source.includes('/components/'), false)
  assert.ok(source.split(/\r?\n/).length < 200)
})

test('feature modules do not depend on Vue components or the root store', () => {
  for (const file of listJavaScriptFiles(`${srcRoot}/features`)) {
    const source = readFileSync(file, 'utf8')
    assert.equal(source.includes('/components/'), false, file)
    assert.equal(/from ['"].*\/store(?:\.js)?['"]/.test(source), false, file)
  }
})

test('the application mounts only the active workspace view', () => {
  const appSource = readFileSync(`${srcRoot}/App.vue`, 'utf8')
  const hostSource = readFileSync(`${srcRoot}/components/ActiveWorkspaceView.vue`, 'utf8')
  const viewNames = [
    'EditorWorkspaceView',
    'TaskManagerView',
    'TemplateRunnerView',
    'DeviceView',
    'DeviceManagerView',
    'RunLogsView',
  ]

  assert.match(appSource, /<ActiveWorkspaceView\s*\/>/)
  assert.match(hostSource, /<component\s+:is="activeComponent"/)
  for (const viewName of viewNames) {
    assert.equal(appSource.includes(`<${viewName} />`), false, viewName)
    const viewSource = readFileSync(`${srcRoot}/components/${viewName}.vue`, 'utf8')
    assert.equal(viewSource.includes('v-show="state.activeView.value'), false, viewName)
  }
  assert.equal(hostSource.includes('ProjectWorkspaceView'), false)
  assert.equal(hostSource.includes("blockly: BlocklyView"), false)
})

test('the unified editor dispatches project files and keeps Blockly overlays theme-aware', () => {
  const editorSource = readFileSync(`${srcRoot}/components/EditorWorkspaceView.vue`, 'utf8')
  const codeEditorSource = readFileSync(`${srcRoot}/components/editor/TextCodeEditor.vue`, 'utf8')
  const blocklyCss = readFileSync(`${srcRoot}/blockly/blockly.css`, 'utf8')

  assert.match(editorSource, /BlocklyEditorPane/)
  assert.match(editorSource, /TextCodeEditor/)
  assert.match(editorSource, /LuaPreviewDrawer/)
  assert.match(codeEditorSource, /StreamLanguage\.define\(lua\)/)
  assert.match(blocklyCss, /\.blocklyWidgetDiv \.blocklyMenu/)
  assert.doesNotMatch(blocklyCss, /\[data-theme\] \.blocklyWidgetDiv/)
  assert.match(blocklyCss, /\.blocklyMenuItemHighlight[\s\S]*var\(--color-primary-soft\)/)
  assert.match(blocklyCss, /\.blocklyMenuItemDisabled/)
  assert.match(blocklyCss, /\.blocklyShortcut/)
})

test('the unified editor can collapse and resize the project tree from its toolbar', () => {
  const editorSource = readFileSync(`${srcRoot}/components/EditorWorkspaceView.vue`, 'utf8')

  assert.match(editorSource, /aria-label="projectTreeVisible \? '收起项目树' : '展开项目树'"/)
  assert.match(editorSource, /class="project-tree-resizer"/)
  assert.match(editorSource, /@pointerdown="startProjectTreeResize"/)
  assert.match(editorSource, /--project-tree-width/)
  assert.match(editorSource, /const projectTreeVisible = state\.projectTreeVisible/)
  assert.match(editorSource, /const projectTreeWidth = state\.projectTreeWidth/)
  assert.match(editorSource, /class="project-tree-overlay"/)
})

test('the editor uses file tabs, right-click tree actions, and compact top menus', () => {
  const appSource = readFileSync(`${srcRoot}/App.vue`, 'utf8')
  const editorSource = readFileSync(`${srcRoot}/components/EditorWorkspaceView.vue`, 'utf8')
  const sidebarSource = readFileSync(`${srcRoot}/components/Sidebar.vue`, 'utf8')
  const taskManagerSource = readFileSync(`${srcRoot}/components/TaskManagerView.vue`, 'utf8')

  assert.match(appSource, /activeView === 'editor'[\s\S]*sidebarCollapsed\.value = true/)
  assert.match(editorSource, /v-for="tab in openFiles"/)
  assert.match(editorSource, /documentLabel\(tab\)/)
  assert.match(editorSource, /:node-props="projectTreeNodeProps"/)
  assert.match(editorSource, /trigger="manual"[\s\S]*projectTreeContextOptions/)
  assert.match(editorSource, /class="editor-menubar"/)
  assert.match(editorSource, /label: editorMenuLabel\('编辑信息'\)/)
  assert.match(editorSource, /editorMenuIcon\(CreateOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(RefreshOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(CheckmarkCircleOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(CubeOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(ArrowBackOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(FolderOpenOutline\)/)
  assert.match(editorSource, /editorMenuIcon\(CodeSlashOutline\)/)
  assert.match(editorSource, /:menu-props="projectMenuProps"/)
  assert.match(editorSource, /:menu-props="viewMenuProps"/)
  assert.match(editorSource, /title="编辑项目信息"/)
  assert.match(editorSource, /label: '重命名'/)
  assert.match(editorSource, /Lua 可打包项目/)
  assert.match(editorSource, /Blockly 可打包项目/)
  assert.match(editorSource, /Blockly 单文件/)
  assert.match(editorSource, /Lua 单文件/)
  assert.match(editorSource, /label="作者"/)
  assert.match(editorSource, /label="描述"/)
  assert.match(editorSource, /class="project-detail-grid"/)
  assert.match(editorSource, /expandedProjectKey === project\.key/)
  assert.match(editorSource, /<dt>文件<\/dt><dd>\{\{ project\.file_count \}\} 个<\/dd>/)
  assert.doesNotMatch(editorSource, /project\.package_id \? `\$\{project\.package_id\}/)
  assert.match(editorSource, /label: editorMenuLabel\('自动保存'\)/)
  assert.match(editorSource, /key: 'toggle-auto-save'/)
  assert.match(editorSource, /editorMenuIcon\(CheckmarkOutline, state\.autoSaveFiles\.value\)/)
  assert.match(editorSource, /:menu-props="fileMenuProps"/)
  assert.match(editorSource, />设备<\/n-button>/)
  assert.match(editorSource, /label: editorMenuLabel\('连接设备…'\)/)
  assert.match(editorSource, /label: editorMenuLabel\('选择设备…'\)/)
  assert.match(editorSource, /label: editorMenuLabel\('设备截图'\)/)
  assert.match(editorSource, /label: editorMenuLabel\('截图预览'\)/)
  assert.match(editorSource, /actions\.handleAction\(actions\.doScreencap\)\.catch/)
  assert.doesNotMatch(sidebarSource, /打开截图预览|关闭截图预览|showScreenshot/)
  assert.match(editorSource, /scheduleFileAutosave\(state\.projectSelectedPath\.value\)/)
  assert.match(appSource, /actions\.schedulePreferencesSave\(\)/)
  assert.match(editorSource, /:draggable="!isSingleFileProject"/)
  assert.match(editorSource, /@drop="handleProjectTreeDrop"/)
  assert.match(editorSource, /label: '新建 Lua 文件…'/)
  assert.match(editorSource, /label: '新建 Blockly 文件…'/)
  assert.match(taskManagerSource, /v-model:checked="state\.autoRefresh\.value">自动刷新/)
  assert.doesNotMatch(sidebarSource, /autoRefresh|autoSaveFiles|自动保存 Blockly/)
  assert.match(sidebarSource, /@update:value="applyAppTheme"/)
  assert.equal(editorSource.includes('选择项目文件开始编辑'), false)
})

test('Blockly owns the save shortcut in the unified project editor', () => {
  const paneSource = readFileSync(`${srcRoot}/components/editor/BlocklyEditorPane.vue`, 'utf8')
  const editorSource = readFileSync(`${srcRoot}/components/EditorWorkspaceView.vue`, 'utf8')

  assert.match(paneSource, /event\.ctrlKey \|\| event\.metaKey/)
  assert.match(paneSource, /emit\('save'\)/)
  assert.match(editorSource, /@save="saveFile"/)
  assert.doesNotMatch(editorSource, /StandaloneBlocklyEditor|StandaloneLuaEditor|standaloneMode/)
})

test('the template editor component delegates state and domain behavior', () => {
  const source = readFileSync(`${srcRoot}/components/TemplateEditorModal.vue`, 'utf8')
  const adapterSource = readFileSync(`${srcRoot}/ui/templateEditor/templateEditorComponent.js`, 'utf8')
  assert.match(source, /templateEditorComponent\.js/)
  assert.match(adapterSource, /useTemplateEditor/)
  assert.ok(source.split(/\r?\n/).length < 550)
})
