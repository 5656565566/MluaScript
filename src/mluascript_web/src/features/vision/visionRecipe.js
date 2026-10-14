const MAA_COORDINATE_SHORT_SIDE = 720

function finiteNumber(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function rounded(value) {
  return Math.round(finiteNumber(value))
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, rounded(value)))
}

export function normalizeImageSize(size = {}) {
  return {
    width: Math.max(0, rounded(size.width)),
    height: Math.max(0, rounded(size.height)),
  }
}

function coordinateSize(value, imageSize) {
  const size = normalizeImageSize({
    width: value.imageWidth || imageSize.width,
    height: value.imageHeight || imageSize.height,
  })
  if (!size.width || !size.height) return { image: size, maa: size }
  // 与 MaaFramework 默认短边缩放及长边取整保持一致。
  const scale = MAA_COORDINATE_SHORT_SIDE / Math.min(size.width, size.height)
  return { image: size, maa: { width: Math.round(size.width * scale), height: Math.round(size.height * scale) } }
}

export function normalizeMaaPoint(point = {}, imageSize = {}) {
  if (!point) return null
  const { image: size, maa } = coordinateSize(point, imageSize)
  const x = clamp(point.x, 0, maa.width || Infinity)
  const y = clamp(point.y, 0, maa.height || Infinity)
  return {
    coordinateSpace: 'maa',
    x,
    y,
    rawX: point.rawX ?? (size.width ? Math.round(x * size.width / maa.width) : null),
    rawY: point.rawY ?? (size.height ? Math.round(y * size.height / maa.height) : null),
    imageWidth: point.imageWidth || size.width,
    imageHeight: point.imageHeight || size.height,
  }
}

export function rawToMaaPoint(point = {}, imageSize = {}) {
  const { image: size, maa } = coordinateSize(point, imageSize)
  if (!size.width || !size.height) return normalizeMaaPoint(point, size)
  return normalizeMaaPoint({
    x: finiteNumber(point.rawX ?? point.x) * maa.width / size.width,
    y: finiteNumber(point.rawY ?? point.y) * maa.height / size.height,
    rawX: clamp(point.rawX ?? point.x, 0, size.width),
    rawY: clamp(point.rawY ?? point.y, 0, size.height),
    imageWidth: size.width,
    imageHeight: size.height,
  }, size)
}

export function normalizePoint(point, imageSize = {}) {
  if (!point) return null
  return point.coordinateSpace === 'maa'
    ? normalizeMaaPoint(point, imageSize)
    : rawToMaaPoint(point, imageSize)
}

export function normalizeMaaRoi(roi = {}, imageSize = {}) {
  if (!roi) return null
  const { image: size, maa } = coordinateSize(roi, imageSize)
  const x = clamp(roi.x, 0, maa.width || Infinity)
  const y = clamp(roi.y, 0, maa.height || Infinity)
  const width = clamp(roi.width, 0, (maa.width || Infinity) - x)
  const height = clamp(roi.height, 0, (maa.height || Infinity) - y)
  return {
    coordinateSpace: 'maa',
    x,
    y,
    width,
    height,
    rawX: roi.rawX ?? (size.width ? Math.round(x * size.width / maa.width) : null),
    rawY: roi.rawY ?? (size.height ? Math.round(y * size.height / maa.height) : null),
    rawWidth: roi.rawWidth ?? (size.width ? Math.round(width * size.width / maa.width) : null),
    rawHeight: roi.rawHeight ?? (size.height ? Math.round(height * size.height / maa.height) : null),
    imageWidth: roi.imageWidth || size.width,
    imageHeight: roi.imageHeight || size.height,
  }
}

export function rawToMaaRoi(roi = {}, imageSize = {}) {
  const { image: size, maa } = coordinateSize(roi, imageSize)
  if (!size.width || !size.height) return normalizeMaaRoi(roi, size)
  const rawX = clamp(roi.rawX ?? roi.x, 0, size.width)
  const rawY = clamp(roi.rawY ?? roi.y, 0, size.height)
  const rawWidth = clamp(roi.rawWidth ?? roi.width, 0, size.width - rawX)
  const rawHeight = clamp(roi.rawHeight ?? roi.height, 0, size.height - rawY)
  return normalizeMaaRoi({
    x: rawX * maa.width / size.width,
    y: rawY * maa.height / size.height,
    width: rawWidth * maa.width / size.width,
    height: rawHeight * maa.height / size.height,
    rawX: clamp(rawX, 0, size.width),
    rawY: clamp(rawY, 0, size.height),
    rawWidth,
    rawHeight,
    imageWidth: size.width,
    imageHeight: size.height,
  }, size)
}

export function maaRoiToRaw(roi, imageSize = {}) {
  const normalized = normalizeMaaRoi(roi, imageSize)
  return {
    x: normalized.rawX ?? normalized.x,
    y: normalized.rawY ?? normalized.y,
    width: normalized.rawWidth ?? normalized.width,
    height: normalized.rawHeight ?? normalized.height,
  }
}

export function normalizeRoi(roi, imageSize = {}) {
  if (!roi) return null
  const normalized = roi.coordinateSpace === 'maa'
    ? normalizeMaaRoi(roi, imageSize)
    : rawToMaaRoi(roi, imageSize)
  return normalized.width > 0 && normalized.height > 0 ? normalized : null
}

export function luaString(value) {
  return JSON.stringify(String(value ?? ''))
}

export function roiToLua(roi) {
  if (!roi) return 'nil'
  const normalized = roi.coordinateSpace === 'maa' ? normalizeMaaRoi(roi) : rawToMaaRoi(roi)
  if (!normalized || normalized.width <= 0 || normalized.height <= 0) return 'nil'
  return `{${normalized.x}, ${normalized.y}, ${normalized.width}, ${normalized.height}}`
}

function colorToLua(value) {
  const text = String(value || '').trim().replace(/^#/, '')
  if (!/^[0-9a-f]{6}$/i.test(text)) return 'nil'
  const channels = [0, 2, 4].map(offset => Number.parseInt(text.slice(offset, offset + 2), 16))
  return `{${channels.join(', ')}}`
}

function optionalString(value) {
  return String(value || '').trim() ? luaString(value) : 'nil'
}

export function buildPointLua(point) {
  if (!point) return ''
  const normalized = point.coordinateSpace === 'maa' ? normalizeMaaPoint(point) : rawToMaaPoint(point)
  if (!normalized) return ''
  return `maa.click(${normalized.x}, ${normalized.y})\n`
}

export function buildRoiLua(roi) {
  if (!roi) return ''
  const normalized = roi.coordinateSpace === 'maa' ? normalizeMaaRoi(roi) : rawToMaaRoi(roi)
  return normalized && normalized.width > 0 && normalized.height > 0
    ? `local roi = ${roiToLua(normalized)}\n`
    : ''
}

export function buildColorLua(color) {
  const value = String(color || '').trim()
  if (!/^#[0-9a-f]{6}$/i.test(value)) return ''
  return `local color = ${luaString(value)}\n`
}

export function buildRecognitionLua(recognition = {}, { clickResult = false } = {}) {
  const kind = String(recognition.kind || 'ocr')
  const roi = roiToLua(recognition.roi)
  const image = 'nil'
  let expression = ''

  if (kind === 'template') {
    expression = `maa.find_template('TemplateMatch', ${optionalString(recognition.templatePath)}, ${roi}, ${Number(recognition.threshold ?? 0.8)}, ${image})`
  } else if (kind === 'feature') {
    expression = `maa.find_feature('FeatureMatch', ${optionalString(recognition.templatePath)}, ${roi}, ${image})`
  } else if (kind === 'color') {
    expression = `maa.find_color('ColorMatch', ${colorToLua(recognition.lower)}, ${colorToLua(recognition.upper)}, ${roi}, ${image})`
  } else if (kind === 'nnd') {
    expression = `maa.find_nnd('NND', ${optionalString(recognition.modelPath)}, ${optionalString(recognition.targets)}, ${roi}, ${image})`
  } else {
    expression = `maa.find_ocr('OCR', ${optionalString(recognition.expected)}, ${roi}, ${image})`
  }

  const code = `local result = ${expression}\n`
  return clickResult ? `${code}click_result(result, 0, -5)\n` : code
}

export function buildVisionLua({ mode = 'recognition', point = null, roi = null, recognition = {} } = {}, options = {}) {
  if (mode === 'point') return buildPointLua(point)
  if (mode === 'roi') return buildRoiLua(roi)
  if (mode === 'color') return buildColorLua(options.color)
  return buildRecognitionLua({ ...recognition, roi }, options)
}
