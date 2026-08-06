import { DEFAULT_CUSTOM_COLOR } from './preferences.js'

export const COLOR_THEME_OPTIONS = [
  { label: '经典', value: 'classic' },
  { label: '翡翠', value: 'emerald', seed: '#18a058' },
  { label: '蓝色', value: 'blue', seed: '#2080f0' },
  { label: '紫色', value: 'violet', seed: '#7c3aed' },
  { label: '琥珀', value: 'amber', seed: '#d97706' },
  { label: '红色', value: 'red', seed: '#dc2626' },
  { label: '青色', value: 'cyan', seed: '#0891b2' },
  { label: '自定义', value: 'custom' },
]

const CLASSIC_PALETTES = {
  light: {
    primary: '#18a058',
    primaryHover: '#36ad6a',
    primaryPressed: '#0c7a43',
    primaryForeground: '#ffffff',
    primarySoft: '#d8f3e8',
    primarySoftHover: '#b9e7d4',
    editorAccent: '#e3f2fd',
    editorAccentHover: '#bbdefb',
    editorAccentText: '#1976d2',
  },
  dark: {
    primary: '#63e2b7',
    primaryHover: '#7fe7c4',
    primaryPressed: '#5acea7',
    primaryForeground: '#10231d',
    primarySoft: '#1f4d3d',
    primarySoftHover: '#285f4b',
    editorAccent: '#1e3a5f',
    editorAccentHover: '#2c4a75',
    editorAccentText: '#90caf9',
  },
}

const SEMANTIC_PALETTES = {
  light: {
    info: '#2080f0',
    success: '#18a058',
    warning: '#b7791f',
    danger: '#d03050',
    overlay: 'rgb(0 0 0 / 50%)',
    shadow: 'rgb(0 0 0 / 24%)',
  },
  dark: {
    info: '#70c0e8',
    success: '#63e2b7',
    warning: '#f2c97d',
    danger: '#e88080',
    overlay: 'rgb(0 0 0 / 58%)',
    shadow: 'rgb(0 0 0 / 36%)',
  },
}

const BLOCKLY_UI_PALETTES = {
  light: {
    workspace: '#ffffff',
    toolbox: '#ffffff',
    text: '#222222',
    grid: '#cccccc',
    initialGrid: '#cccccc',
  },
  dark: {
    workspace: '#1a1a1a',
    toolbox: '#181818',
    text: '#d6deeb',
    grid: '#414b5a',
    initialGrid: '#313846',
  },
}

function normalizeHex(color) {
  const value = String(color || '').trim()
  return /^#[0-9a-f]{6}$/i.test(value) ? value.toLowerCase() : DEFAULT_CUSTOM_COLOR
}

function hexToRgb(color) {
  const value = normalizeHex(color).slice(1)
  return [0, 2, 4].map(index => Number.parseInt(value.slice(index, index + 2), 16) / 255)
}

function linearChannel(value) {
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
}

function gammaChannel(value) {
  return value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055
}

function rgbToOklch(color) {
  const [red, green, blue] = hexToRgb(color).map(linearChannel)
  const l = Math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue)
  const m = Math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue)
  const s = Math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue)
  const lightness = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s
  const b = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  return { lightness, chroma: Math.sqrt(a * a + b * b), hue: Math.atan2(b, a) }
}

function oklchToRgb({ lightness, chroma, hue }) {
  const a = chroma * Math.cos(hue)
  const b = chroma * Math.sin(hue)
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
  return [
    gammaChannel(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    gammaChannel(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    gammaChannel(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ]
}

function oklchToHex(value) {
  let candidate = { ...value }
  let rgb = oklchToRgb(candidate)
  // 降低超出 sRGB 色域的色度，避免简单裁剪导致明显偏色。
  for (let attempt = 0; attempt < 24 && rgb.some(channel => channel < 0 || channel > 1); attempt += 1) {
    candidate.chroma *= 0.92
    rgb = oklchToRgb(candidate)
  }
  return `#${rgb.map(channel => Math.round(Math.max(0, Math.min(1, channel)) * 255).toString(16).padStart(2, '0')).join('')}`
}

function tone(seed, lightness, chromaScale = 1) {
  const source = rgbToOklch(seed)
  return oklchToHex({
    lightness,
    chroma: Math.min(0.24, source.chroma * chromaScale),
    hue: source.hue,
  })
}

function relativeLuminance(color) {
  const [red, green, blue] = hexToRgb(color).map(linearChannel)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrastRatio(left, right) {
  const [bright, dark] = [relativeLuminance(left), relativeLuminance(right)].sort((a, b) => b - a)
  return (bright + 0.05) / (dark + 0.05)
}

function foregroundFor(background) {
  const light = '#f8fafc'
  const dark = '#111827'
  const preferLight = contrastRatio(background, light) >= contrastRatio(background, dark)
  const preferred = preferLight ? light : dark
  if (contrastRatio(background, preferred) >= 4.5) return preferred
  // 极高饱和度的中间亮度颜色可能无法搭配柔和黑白，必要时退到最大对比前景色。
  return preferLight ? '#ffffff' : '#000000'
}

function rgba(color, alpha) {
  const [red, green, blue] = hexToRgb(color).map(value => Math.round(value * 255))
  return `rgb(${red} ${green} ${blue} / ${alpha})`
}

function buildGeneratedPalette(seedColor, dark) {
  const seed = normalizeHex(seedColor)
  const seedTone = rgbToOklch(seed)
  const primary = dark
    ? tone(seed, Math.max(0.70, Math.min(0.82, seedTone.lightness + 0.10)))
    : tone(seed, Math.max(0.48, Math.min(0.62, seedTone.lightness)))
  return {
    primary,
    primaryHover: tone(seed, dark ? 0.82 : 0.56),
    primaryPressed: tone(seed, dark ? 0.68 : 0.46),
    primaryForeground: foregroundFor(primary),
    primarySoft: tone(seed, dark ? 0.27 : 0.94, dark ? 0.48 : 0.28),
    primarySoftHover: tone(seed, dark ? 0.34 : 0.88, dark ? 0.58 : 0.42),
    editorAccent: tone(seed, dark ? 0.25 : 0.95, dark ? 0.42 : 0.24),
    editorAccentHover: tone(seed, dark ? 0.33 : 0.89, dark ? 0.54 : 0.38),
    editorAccentText: tone(seed, dark ? 0.80 : 0.48),
  }
}

export function isDarkTheme(themeMode, browserWindow = window) {
  return themeMode === 'dark'
    || (themeMode === 'system' && browserWindow.matchMedia('(prefers-color-scheme: dark)').matches)
}

export function getBlocklyUiPalette(dark) {
  return BLOCKLY_UI_PALETTES[dark ? 'dark' : 'light']
}

export function buildThemePalette(colorTheme = 'classic', customColor = DEFAULT_CUSTOM_COLOR, dark = false) {
  const classic = CLASSIC_PALETTES[dark ? 'dark' : 'light']
  const theme = COLOR_THEME_OPTIONS.find(option => option.value === colorTheme)
  const generated = !theme || theme.value === 'classic'
    ? classic
    : buildGeneratedPalette(theme.value === 'custom' ? customColor : theme.seed, dark)
  const semantic = SEMANTIC_PALETTES[dark ? 'dark' : 'light']
  return {
    ...generated,
    ...semantic,
    focusRing: rgba(generated.primary, dark ? 0.52 : 0.38),
    selection: rgba(generated.editorAccentText, dark ? 0.30 : 0.20),
  }
}

export function buildNaiveThemeOverrides(colorTheme, customColor, dark) {
  const palette = buildThemePalette(colorTheme, customColor, dark)
  return {
    common: {
      primaryColor: palette.primary,
      primaryColorHover: palette.primaryHover,
      primaryColorPressed: palette.primaryPressed,
      primaryColorSuppl: palette.primaryHover,
      infoColor: palette.info,
      successColor: palette.success,
      warningColor: palette.warning,
      errorColor: palette.danger,
    },
    Button: {
      textColorPrimary: palette.primaryForeground,
      textColorHoverPrimary: palette.primaryForeground,
      textColorPressedPrimary: palette.primaryForeground,
      textColorFocusPrimary: palette.primaryForeground,
    },
  }
}

export function applyThemeVariables(document, colorTheme, customColor, dark) {
  const palette = buildThemePalette(colorTheme, customColor, dark)
  const rootStyle = document.documentElement.style
  const variables = {
    '--color-primary': palette.primary,
    '--color-primary-hover': palette.primaryHover,
    '--color-primary-pressed': palette.primaryPressed,
    '--color-primary-foreground': palette.primaryForeground,
    '--color-primary-soft': palette.primarySoft,
    '--color-primary-soft-hover': palette.primarySoftHover,
    '--color-accent': palette.editorAccent,
    '--color-accent-hover': palette.editorAccentHover,
    '--color-accent-text': palette.editorAccentText,
    '--color-focus-ring': palette.focusRing,
    '--color-selection': palette.selection,
    '--color-info': palette.info,
    '--color-success': palette.success,
    '--color-warning': palette.warning,
    '--color-danger': palette.danger,
    '--color-overlay': palette.overlay,
    '--color-shadow': palette.shadow,
  }
  for (const [name, value] of Object.entries(variables)) rootStyle.setProperty?.(name, value)
  return palette
}

export function colorThemePreview(colorTheme, customColor = DEFAULT_CUSTOM_COLOR, dark = false) {
  const palette = buildThemePalette(colorTheme, customColor, dark)
  return `linear-gradient(135deg, ${palette.editorAccent} 0 34%, ${palette.primarySoft} 34% 67%, ${palette.primary} 67% 100%)`
}
