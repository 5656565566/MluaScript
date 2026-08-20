import test from 'node:test'
import assert from 'node:assert/strict'
import { buildColorLua, buildPointLua, buildRecognitionLua, buildRoiLua, normalizeRoi, rawToMaaPoint, rawToMaaRoi, roiToLua } from '../src/features/vision/visionRecipe.js'

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
