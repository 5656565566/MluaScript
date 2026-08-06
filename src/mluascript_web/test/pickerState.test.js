import test from 'node:test'
import assert from 'node:assert/strict'

import { mergePickerHandlers } from '../src/store/pickerConfig.js'

test('picker step updates can clear handlers from the previous step', () => {
  const onSelect = () => {}
  const onManage = () => {}
  const handlers = mergePickerHandlers({ onSelect, onManage }, { onManage: null })

  assert.equal(handlers.onSelect, onSelect)
  assert.equal(handlers.onManage, null)
})
