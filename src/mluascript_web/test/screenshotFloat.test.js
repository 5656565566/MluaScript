import test from 'node:test'
import assert from 'node:assert/strict'

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const srcRoot = fileURLToPath(new URL('../src/', import.meta.url))

test('screenshot preview formats zoom to two decimal places and supports right-button panning', () => {
  const source = readFileSync(`${srcRoot}/components/ScreenshotFloat.vue`, 'utf8')

  assert.match(source, /Math\.round\(Math\.max\(MIN_ZOOM, Math\.min\(MAX_ZOOM, nextZoom\)\) \* 100\) \/ 100/)
  assert.match(source, /Number\(value\)\.toFixed\(2\)/)
  assert.match(source, /event\.button !== 2/)
  assert.match(source, /@contextmenu="handleContextMenu"/)
  assert.match(source, /@mousedown="handlePanStart"/)
  assert.match(source, />上传图片<\/n-button>/)
  assert.match(source, /name="color"[\s\S]*<span>颜色拾取<\/span>/)
  assert.match(source, /getImageData\(0, 0, 1, 1\)/)
  assert.match(source, /clipboardOptions/)
  assert.match(source, /insertOptions/)
  assert.match(source, /label="保存位置"/)
  assert.match(source, /save-directory-browser/)
  assert.match(source, /save-directory-breadcrumb/)
  assert.match(source, /saveDirectoryNodes/)
  assert.match(source, /navigateSaveDirectory/)
  assert.doesNotMatch(source, />打开识图调试<\/n-button>/)
})
