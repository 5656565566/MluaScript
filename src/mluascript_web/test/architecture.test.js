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
