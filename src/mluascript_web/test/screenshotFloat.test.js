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
  assert.match(source, /name="color" tab="颜色拾取"/)
  assert.match(source, /getImageData\(0, 0, 1, 1\)/)
})
