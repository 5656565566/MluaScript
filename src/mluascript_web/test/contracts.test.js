import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeConnection,
  normalizeDesktopItem,
  normalizeDeviceItem,
  normalizeDeviceItems,
} from '../src/api/contracts.js'

test('normalizeDeviceItem accepts the backend device contract', () => {
  assert.deepEqual(normalizeDeviceItem({
    id: 'adb:127.0.0.1:5555',
    kind: 'adb',
    title: 'Android',
    subtitle: '127.0.0.1:5555',
    enabled: false,
    tags: ['manual'],
  }), {
    id: 'adb:127.0.0.1:5555',
    kind: 'adb',
    name: 'Android',
    address: '127.0.0.1:5555',
    enabled: false,
    tags: ['manual'],
    handle: null,
  })
})

test('normalizeDeviceItems always returns a frontend collection', () => {
  assert.deepEqual(normalizeDeviceItems(null), [])
  assert.equal(normalizeDeviceItems([{ title: 'Browser' }])[0].name, 'Browser')
})

test('normalizeDesktopItem preserves the desktop handle aliases', () => {
  const item = normalizeDesktopItem({ id: 'desktop:42', title: 'Window', handle: 42 })
  assert.equal(item.window_name, 'Window')
  assert.equal(item.hwnd, 42)
  assert.equal(item.handle, 42)
})

test('normalizeConnection accepts snake case and camel case capabilities', () => {
  assert.equal(normalizeConnection({ can_screencap: true }).canScreencap, true)
  assert.equal(normalizeConnection({ canScreencap: true }).canScreencap, true)
})
