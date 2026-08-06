import test from 'node:test'
import assert from 'node:assert/strict'

import { createUiState } from '../src/app/uiState.js'
import { applyWebPreferences, buildWebPreferences } from '../src/app/preferences.js'

test('web preferences hydrate persistent appearance and editor settings', () => {
  const state = createUiState()
  applyWebPreferences(state, {
    appearance: { themeMode: 'dark', colorTheme: 'custom', customColor: '#2080f0', paletteVersion: 1 },
    editor: { autoSaveFiles: false, projectTreeVisible: false, projectTreeWidth: 312 },
    tasks: { autoRefresh: false, activeTab: 'task-status' },
    logs: { autoScroll: false, selectedLevel: 'ERROR', origin: 'web' },
    layout: { sidebarCollapsed: true, activeView: 'run-logs' },
  })

  assert.equal(state.appTheme.value, 'dark')
  assert.equal(state.colorTheme.value, 'custom')
  assert.equal(state.customColor.value, '#2080f0')
  assert.equal(state.autoSaveFiles.value, false)
  assert.equal(state.projectTreeVisible.value, false)
  assert.equal(state.projectTreeWidth.value, 312)
  assert.equal(state.preferencesHydrated.value, true)
  assert.equal(buildWebPreferences(state).tasks.activeTab, 'task-status')
})

test('invalid appearance and tree preference values fall back safely', () => {
  const state = createUiState()

  applyWebPreferences(state, {
    appearance: { themeMode: 'unknown', colorTheme: 'unknown', customColor: 'yellow' },
    editor: { projectTreeWidth: 9999 },
  })

  assert.equal(state.appTheme.value, 'system')
  assert.equal(state.colorTheme.value, 'classic')
  assert.equal(state.customColor.value, '#18a058')
  assert.equal(state.projectTreeWidth.value, 420)
  assert.equal(state.autoSaveFiles.value, true)
})

test('legacy accent preference becomes a custom color theme', () => {
  const state = createUiState()

  applyWebPreferences(state, { appearance: { accentColor: '#2080f0' } })

  assert.equal(state.colorTheme.value, 'custom')
  assert.equal(state.customColor.value, '#2080f0')
  assert.equal(buildWebPreferences(state).appearance.colorTheme, 'custom')
  assert.equal('accentColor' in buildWebPreferences(state).appearance, false)
})
