import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as Blockly from 'blockly'
import '@blockly/field-slider'

const srcRoot = fileURLToPath(new URL('../src/', import.meta.url))

test('template threshold uses a replaceable slider shadow', () => {
  const Slider = Blockly.registry.getClass(Blockly.registry.Type.FIELD, 'field_slider')
  const field = Slider.fromJson({ value: 0.8, min: 0, max: 1, precision: 0.01 })
  field.setValue(0.85)
  assert.equal(field.getValue(), 0.85)
  field.setValue(2)
  assert.equal(field.getValue(), 1)

  const visionSource = readFileSync(`${srcRoot}/blockly/blocks/vision.js`, 'utf8')
  const toolboxSource = readFileSync(`${srcRoot}/blockly/toolbox.js`, 'utf8')
  const insertionSource = readFileSync(`${srcRoot}/blockly/visionInsertion.js`, 'utf8')
  const styleSource = readFileSync(`${srcRoot}/blockly/blockly.css`, 'utf8')

  assert.match(visionSource, /type: 'maa_common_threshold',[\s\S]*message0: '常用阈值 %1',[\s\S]*type: 'field_dropdown'/)
  assert.match(visionSource, /type: 'maa_default_threshold',[\s\S]*message0: '阈值 %1',[\s\S]*type: 'field_slider'/)
  assert.match(visionSource, /type: 'field_slider',[\s\S]*value: 0\.8,[\s\S]*min: 0,[\s\S]*max: 1,[\s\S]*precision: 0\.01/)
  assert.match(visionSource, /toolboxInputs:[\s\S]*THRESHOLD:[\s\S]*type: 'maa_default_threshold'/)
  assert.match(visionSource, /type: 'input_value', name: 'THRESHOLD', check: 'Number'/)
  assert.match(toolboxSource, /if \(spec\.toolboxInputs\) blockItem\.inputs = spec\.toolboxInputs/)
  assert.match(insertionSource, /connectValue\(block, 'THRESHOLD', thresholdBlock\(workspace, recognition\.threshold \?\? 0\.8\)\)/)
  assert.match(insertionSource, /block\.setShadow\(true\)/)
  assert.match(styleSource, /\.blocklyDropDownDiv:not\(:has\(\.fieldSliderContainer\)\)/)
  assert.match(styleSource, /\.blocklyWidgetDiv \.blocklyHtmlInput,/)
  assert.match(styleSource, /background-color: transparent !important/)
  assert.match(styleSource, /color: var\(--blockly-field-text\) !important/)
})
