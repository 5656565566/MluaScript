export const MAA_COORDINATE_WIDTH = 1280
export const MAA_COORDINATE_HEIGHT = 720

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

export function normalizeMaaPoint(point = {}, imageSize = {}) {
  if (!point) return null
  const size = normalizeImageSize(imageSize)
  const x = clamp(point.x, 0, MAA_COORDINATE_WIDTH)
  const y = clamp(point.y, 0, MAA_COORDINATE_HEIGHT)
  return {
    coordinateSpace: 'maa',
    x,
    y,
    rawX: point.rawX ?? (size.width ? Math.round(x * size.width / MAA_COORDINATE_WIDTH) : null),
    rawY: point.rawY ?? (size.height ? Math.round(y * size.height / MAA_COORDINATE_HEIGHT) : null),
    imageWidth: point.imageWidth || size.width,
    imageHeight: point.imageHeight || size.height,
  }
}

export function rawToMaaPoint(point = {}, imageSize = {}) {
  const size = normalizeImageSize({
    width: point.imageWidth || imageSize.width,
    height: point.imageHeight || imageSize.height,
  })
  if (!size.width || !size.height) return normalizeMaaPoint(point, size)
  return normalizeMaaPoint({
    x: finiteNumber(point.rawX ?? point.x) * MAA_COORDINATE_WIDTH / size.width,
    y: finiteNumber(point.rawY ?? point.y) * MAA_COORDINATE_HEIGHT / size.height,
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
  const size = normalizeImageSize(imageSize)
  const x = clamp(roi.x, 0, MAA_COORDINATE_WIDTH)
  const y = clamp(roi.y, 0, MAA_COORDINATE_HEIGHT)
  const width = clamp(roi.width, 0, MAA_COORDINATE_WIDTH - x)
  const height = clamp(roi.height, 0, MAA_COORDINATE_HEIGHT - y)
  return {
    coordinateSpace: 'maa',
    x,
    y,
    width,
    height,
    rawX: roi.rawX ?? (size.width ? Math.round(x * size.width / MAA_COORDINATE_WIDTH) : null),
    rawY: roi.rawY ?? (size.height ? Math.round(y * size.height / MAA_COORDINATE_HEIGHT) : null),
    rawWidth: roi.rawWidth ?? (size.width ? Math.round(width * size.width / MAA_COORDINATE_WIDTH) : null),
    rawHeight: roi.rawHeight ?? (size.height ? Math.round(height * size.height / MAA_COORDINATE_HEIGHT) : null),
    imageWidth: roi.imageWidth || size.width,
    imageHeight: roi.imageHeight || size.height,
  }
}

export function rawToMaaRoi(roi = {}, imageSize = {}) {
  const size = normalizeImageSize({
    width: roi.imageWidth || imageSize.width,
    height: roi.imageHeight || imageSize.height,
  })
  if (!size.width || !size.height) return normalizeMaaRoi(roi, size)
  const rawX = finiteNumber(roi.rawX ?? roi.x)
  const rawY = finiteNumber(roi.rawY ?? roi.y)
  const rawWidth = finiteNumber(roi.rawWidth ?? roi.width)
  const rawHeight = finiteNumber(roi.rawHeight ?? roi.height)
  return normalizeMaaRoi({
    x: rawX * MAA_COORDINATE_WIDTH / size.width,
    y: rawY * MAA_COORDINATE_HEIGHT / size.height,
    width: rawWidth * MAA_COORDINATE_WIDTH / size.width,
    height: rawHeight * MAA_COORDINATE_HEIGHT / size.height,
    rawX: clamp(rawX, 0, size.width),
    rawY: clamp(rawY, 0, size.height),
    rawWidth: clamp(rawWidth, 0, size.width),
    rawHeight: clamp(rawHeight, 0, size.height),
    imageWidth: size.width,
    imageHeight: size.height,
  }, size)
}

export function maaRoiToRaw(roi, imageSize = {}) {
  const size = normalizeImageSize(imageSize)
  const normalized = normalizeMaaRoi(roi, size)
  return {
    x: normalized.rawX ?? (size.width ? Math.round(normalized.x * size.width / MAA_COORDINATE_WIDTH) : normalized.x),
    y: normalized.rawY ?? (size.height ? Math.round(normalized.y * size.height / MAA_COORDINATE_HEIGHT) : normalized.y),
    width: normalized.rawWidth ?? (size.width ? Math.round(normalized.width * size.width / MAA_COORDINATE_WIDTH) : normalized.width),
    height: normalized.rawHeight ?? (size.height ? Math.round(normalized.height * size.height / MAA_COORDINATE_HEIGHT) : normalized.height),
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
