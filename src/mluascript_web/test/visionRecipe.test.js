import test from 'node:test'
import assert from 'node:assert/strict'
import { buildColorLua, buildPointLua, buildRecognitionLua, buildRoiLua, maaRoiToRaw, normalizeRoi, rawToMaaPoint, rawToMaaRoi, roiToLua } from '../src/features/vision/visionRecipe.js'

test('vision recipes normalize ROI and generate Lua for point and recognition actions', () => {
  assert.deepEqual(rawToMaaPoint({ rawX: 960, rawY: 360, imageWidth: 1920, imageHeight: 1080 }), {
    coordinateSpace: 'maa',
    x: 640,
    y: 240,
    rawX: 960,
    rawY: 360,
    imageWidth: 1920,
    imageHeight: 1080,
  })
  assert.deepEqual(rawToMaaRoi({ rawX: 960, rawY: 360, rawWidth: 480, rawHeight: 180, imageWidth: 1920, imageHeight: 1080 }), {
    coordinateSpace: 'maa',
    x: 640,
    y: 240,
    width: 320,
    height: 120,
    rawX: 960,
    rawY: 360,
    rawWidth: 480,
    rawHeight: 180,
    imageWidth: 1920,
    imageHeight: 1080,
  })
  assert.deepEqual(normalizeRoi({ x: 10, y: 20, width: 100, height: 50 }, { width: 1920, height: 1080 }).coordinateSpace, 'maa')
  assert.equal(roiToLua({ x: 640, y: 240, width: 320, height: 120, coordinateSpace: 'maa' }), '{640, 240, 320, 120}')
  assert.equal(buildRoiLua({ x: 640, y: 240, width: 320, height: 120, coordinateSpace: 'maa' }), 'local roi = {640, 240, 320, 120}\n')
  assert.equal(buildPointLua({ x: 640, y: 240, coordinateSpace: 'maa' }), 'maa.click(640, 240)\n')
  assert.equal(buildColorLua('#12AbEF'), 'local color = "#12AbEF"\n')
  assert.match(buildRecognitionLua({
    kind: 'template',
    templatePath: 'assets:button.png',
    roi: { x: 10, y: 20, width: 100, height: 50 },
    threshold: 0.8,
  }, { clickResult: true }), /maa\.find_template\('TemplateMatch', "assets:button\.png", \{10, 20, 100, 50\}, 0\.8, nil\)/)
  assert.match(buildRecognitionLua({ kind: 'ocr', expected: '确定' }), /maa\.find_ocr\('OCR', "确定", nil, nil\)/)
})

for (const [imageWidth, imageHeight, expectedX, expectedY] of [
  [2400, 1080, 800, 360],
  [1080, 2400, 360, 800],
  [1600, 720, 800, 360],
  [720, 1600, 360, 800],
  [1024, 768, 480, 360],
  [1080, 1920, 360, 640],
]) {
  test(`point and ROI preserve aspect ratio for ${imageWidth}x${imageHeight}`, () => {
    const point = rawToMaaPoint({ rawX: imageWidth / 2, rawY: imageHeight / 2, imageWidth, imageHeight })
    assert.equal(buildPointLua(point), `maa.click(${expectedX}, ${expectedY})\n`)
    const roi = rawToMaaRoi({ rawX: imageWidth / 2, rawY: imageHeight / 2, rawWidth: imageWidth / 4, rawHeight: imageHeight / 4, imageWidth, imageHeight })
    assert.equal(roiToLua(roi), `{${expectedX}, ${expectedY}, ${expectedX / 2}, ${expectedY / 2}}`)
    assert.deepEqual(maaRoiToRaw(roi, { width: imageWidth, height: imageHeight }), {
      x: imageWidth / 2, y: imageHeight / 2, width: imageWidth / 4, height: imageHeight / 4,
    })
    assert.equal(buildPointLua({ coordinateSpace: 'maa', x: expectedX, y: expectedY }), `maa.click(${expectedX}, ${expectedY})\n`)
  })
}

test('ROI clamps against the actual image edges and uses Maa long-side rounding', () => {
  const roi = rawToMaaRoi({ x: 700, y: 1500, width: 100, height: 200, imageWidth: 720, imageHeight: 1600 })
  assert.equal(roiToLua(roi), '{700, 1500, 20, 100}')
  assert.deepEqual(maaRoiToRaw(roi), { x: 700, y: 1500, width: 20, height: 100 })
  const point = rawToMaaPoint({ x: 2000, y: 1001, imageWidth: 2000, imageHeight: 1001 })
  assert.equal(point.x, 1439)
  assert.equal(point.y, 720)
})
