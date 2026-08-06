import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyThemeVariables,
  buildNaiveThemeOverrides,
  buildThemePalette,
  colorThemePreview,
} from '../src/app/theme.js'

function relativeLuminance(color) {
  const channels = [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16) / 255)
  const [red, green, blue] = channels.map(value => (
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  ))
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrastRatio(left, right) {
  const values = [relativeLuminance(left), relativeLuminance(right)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}


test('classic theme preserves the original multi-color light and dark palettes', () => {
  const light = buildThemePalette('classic', '#dc2626', false)
  const dark = buildThemePalette('classic', '#dc2626', true)

  assert.equal(light.primary, '#18a058')
  assert.equal(light.editorAccent, '#e3f2fd')
  assert.equal(light.editorAccentText, '#1976d2')
  assert.equal(dark.primary, '#63e2b7')
  assert.equal(dark.editorAccent, '#1e3a5f')
  assert.equal(dark.editorAccentText, '#90caf9')
})


test('custom seed generates complete and distinct light and dark palettes', () => {
  const light = buildThemePalette('custom', '#facc15', false)
  const dark = buildThemePalette('custom', '#facc15', true)

  for (const key of ['primary', 'primaryHover', 'primarySoft', 'editorAccent', 'editorAccentText']) {
    assert.match(light[key], /^#[0-9a-f]{6}$/)
    assert.match(dark[key], /^#[0-9a-f]{6}$/)
  }
  assert.notEqual(light.primary, dark.primary)
  assert.notEqual(light.editorAccent, dark.editorAccent)
  assert.ok(['#f8fafc', '#111827', '#ffffff', '#000000'].includes(light.primaryForeground))
  assert.equal(buildNaiveThemeOverrides('custom', '#facc15', false).Button.textColorPrimary, light.primaryForeground)
})


test('generated primary colors keep readable text for extreme custom seeds', () => {
  for (const seed of ['#000000', '#ffffff', '#facc15', '#0000ff', '#ff00ff']) {
    for (const dark of [false, true]) {
      const palette = buildThemePalette('custom', seed, dark)
      assert.ok(
        contrastRatio(palette.primary, palette.primaryForeground) >= 4.5,
        `${seed} ${dark ? 'dark' : 'light'} primary contrast`,
      )
    }
  }
})


test('theme application writes interaction and semantic variables', () => {
  const variables = new Map()
  const document = {
    documentElement: {
      style: { setProperty: (name, value) => variables.set(name, value) },
    },
  }

  applyThemeVariables(document, 'violet', '#18a058', false)

  assert.match(variables.get('--color-primary'), /^#[0-9a-f]{6}$/)
  assert.match(variables.get('--color-accent-text'), /^#[0-9a-f]{6}$/)
  assert.equal(variables.get('--color-danger'), '#d03050')
  assert.match(colorThemePreview('violet'), /^linear-gradient/)
})
