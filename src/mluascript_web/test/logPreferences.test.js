import test from 'node:test'
import assert from 'node:assert/strict'
import { createUiState } from '../src/app/uiState.js'
import { applyWebPreferences, buildWebPreferences } from '../src/app/preferences.js'

test('run logs default to the application channel that contains device errors', () => {
  const state = createUiState()
  assert.equal(state.logOrigin.value, 'default')
  applyWebPreferences(state)
  assert.equal(state.logOrigin.value, 'default')
})

test('old runtime channel preferences migrate without overwriting explicit channels', () => {
  const state = createUiState()
  applyWebPreferences(state, { logs: { origin: 'runtime', selectedLevel: 'ERROR' } })
  assert.equal(buildWebPreferences(state).logs.origin, 'default')
  assert.equal(state.runLogsSelectedLevel.value, 'ERROR')
  applyWebPreferences(state, { logs: { origin: 'runtime.log' } })
  assert.equal(state.logOrigin.value, 'runtime.log')
})
