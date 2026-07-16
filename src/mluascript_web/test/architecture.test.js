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
    'BlocklyView',
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
})

test('the template editor component delegates state and domain behavior', () => {
  const source = readFileSync(`${srcRoot}/components/TemplateEditorModal.vue`, 'utf8')
  const adapterSource = readFileSync(`${srcRoot}/ui/templateEditor/templateEditorComponent.js`, 'utf8')
  assert.match(source, /templateEditorComponent\.js/)
  assert.match(adapterSource, /useTemplateEditor/)
  assert.ok(source.split(/\r?\n/).length < 550)
})
