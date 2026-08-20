import * as Blockly from 'blockly'

function finishBlock(block) {
  block.initSvg?.()
  block.render?.()
  return block
}

function textBlock(workspace, value) {
  const block = finishBlock(workspace.newBlock('text'))
  block.setFieldValue(String(value ?? ''), 'TEXT')
  return block
}

function numberBlock(workspace, value) {
  const block = finishBlock(workspace.newBlock('math_number'))
  block.setFieldValue(String(Number(value) || 0), 'NUM')
  return block
}

function connectValue(parent, inputName, child) {
  const connection = parent.getInput(inputName)?.connection
  if (!connection || !child?.outputConnection) return
  connection.connect(child.outputConnection)
}

function createValueBlock(workspace, value) {
  return typeof value === 'number' ? numberBlock(workspace, value) : textBlock(workspace, value)
}

function createRoiBlock(workspace, roi) {
  if (!roi || Number(roi.width) <= 0 || Number(roi.height) <= 0) {
    return finishBlock(workspace.newBlock('maa_roi_fullscreen'))
  }
  const block = finishBlock(workspace.newBlock('maa_roi_rect'))
  connectValue(block, 'X', numberBlock(workspace, roi.x))
  connectValue(block, 'Y', numberBlock(workspace, roi.y))
  connectValue(block, 'W', numberBlock(workspace, roi.width))
  connectValue(block, 'H', numberBlock(workspace, roi.height))
  return block
}

function createRecognitionBlock(workspace, recognition, roi) {
  const kind = String(recognition?.kind || 'ocr')
  const typeByKind = {
    ocr: 'maa_find_ocr',
    template: 'maa_find_template',
    feature: 'maa_find_feature',
    color: 'maa_find_color',
    nnd: 'maa_find_nnd',
  }
  const block = finishBlock(workspace.newBlock(typeByKind[kind] || typeByKind.ocr))
  connectValue(block, 'ROI', createRoiBlock(workspace, roi))

  if (kind === 'template' || kind === 'feature') {
    connectValue(block, 'TEMPLATE', textBlock(workspace, recognition.templatePath))
  } else if (kind === 'ocr') {
    connectValue(block, 'EXPECTED', textBlock(workspace, recognition.expected))
  } else if (kind === 'nnd') {
    connectValue(block, 'MODEL', textBlock(workspace, recognition.modelPath))
    connectValue(block, 'TARGETS', textBlock(workspace, recognition.targets))
  } else if (kind === 'color') {
    connectValue(block, 'LOWER', textBlock(workspace, recognition.lower || '#000000'))
    connectValue(block, 'UPPER', textBlock(workspace, recognition.upper || '#ffffff'))
  }

  if (kind === 'template') {
    connectValue(block, 'THRESHOLD', numberBlock(workspace, recognition.threshold ?? 0.8))
  }
  return block
}

function placeBlock(workspace, block) {
  const topBlocks = workspace.getTopBlocks(false)
  const offset = topBlocks.length * 48
  block.moveBy?.(48 + offset, 48 + offset)
  block.select?.()
  workspace.render?.()
}

export function insertVisionRecipeIntoBlockly(workspace, recipe = {}) {
  if (!workspace || typeof workspace.newBlock !== 'function') throw new Error('Blockly 工作区不可用')
  const mode = recipe.mode || 'recognition'
  const group = Blockly.Events.getGroup?.() || Blockly.utils.idGenerator.genUid()
  Blockly.Events.setGroup?.(group)
  try {
    if (mode === 'point') {
      const point = recipe.point || {}
      const block = finishBlock(workspace.newBlock('maa_click'))
      connectValue(block, 'X', numberBlock(workspace, point.x))
      connectValue(block, 'Y', numberBlock(workspace, point.y))
      placeBlock(workspace, block)
      return block
    }

    if (mode === 'roi') {
      const block = createRoiBlock(workspace, recipe.roi)
      placeBlock(workspace, block)
      return block
    }

    if (mode === 'color') {
      const block = finishBlock(workspace.newBlock('maa_color_hex'))
      block.setFieldValue(String(recipe.color || '#000000'), 'COLOR')
      placeBlock(workspace, block)
      return block
    }

    const recognition = createRecognitionBlock(workspace, recipe.recognition || {}, recipe.roi)
    if (!recipe.clickResult) {
      placeBlock(workspace, recognition)
      return recognition
    }

    const click = finishBlock(workspace.newBlock('maa_click_result'))
    connectValue(click, 'RESULT', recognition)
    connectValue(click, 'OFFSET_X', numberBlock(workspace, recipe.offsetX ?? 0))
    connectValue(click, 'OFFSET_Y', numberBlock(workspace, recipe.offsetY ?? -5))
    placeBlock(workspace, click)
    return click
  } finally {
    Blockly.Events.setGroup?.(false)
  }
}
