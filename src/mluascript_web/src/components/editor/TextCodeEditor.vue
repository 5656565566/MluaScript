<script setup>
import { onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { state } from '../../store'
import { Compartment, EditorState, Prec } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { StreamLanguage } from '@codemirror/language'
import { json } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { xml } from '@codemirror/lang-xml'
import { yaml } from '@codemirror/lang-yaml'
import { lua } from '@codemirror/legacy-modes/mode/lua'
import { oneDark } from '@codemirror/theme-one-dark'

const props = defineProps({
  modelValue: { type: String, default: '' },
  path: { type: String, default: '' },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])
const hostRef = shallowRef(null)
const viewRef = shallowRef(null)
const themeCompartment = new Compartment()
let applyingExternalValue = false
let themeObserver = null

const luaLanguage = StreamLanguage.define(lua)

function languageExtension(path) {
  const suffix = String(path || '').toLowerCase().split('.').pop()
  if (suffix === 'lua') return luaLanguage
  if (suffix === 'json') return json()
  if (suffix === 'xml') return xml()
  if (suffix === 'yaml' || suffix === 'yml') return yaml()
  if (suffix === 'md' || suffix === 'markdown') return markdown()
  return []
}

const sharedTheme = EditorView.theme({
  '&': {
    height: '100%',
    backgroundColor: 'var(--color-surface)',
    color: 'var(--color-text-primary)',
    fontSize: '13px',
  },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': {
    overflow: 'auto',
    fontFamily: "'Cascadia Code', 'JetBrains Mono', Consolas, monospace",
    lineHeight: '1.6',
  },
  '.cm-content': { minHeight: '100%', padding: '12px 0' },
  '.cm-line': { padding: '0 14px' },
  '.cm-gutters': {
    backgroundColor: 'var(--color-surface-2)',
    color: 'var(--color-text-secondary)',
    borderRight: '1px solid var(--color-border)',
  },
  '.cm-activeLine, .cm-activeLineGutter': {
    backgroundColor: 'color-mix(in srgb, var(--color-accent-text) 9%, transparent)',
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: 'color-mix(in srgb, var(--color-accent-text) 28%, transparent) !important',
  },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--color-accent-text)' },
})

function currentThemeExtensions() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark'
  return dark ? [oneDark, sharedTheme] : [sharedTheme]
}

function createEditor() {
  if (!hostRef.value) return
  const saveKeymap = Prec.high(keymap.of([{
    key: 'Mod-s',
    preventDefault: true,
    run() {
      if (!props.readOnly) emit('save')
      return true
    },
  }]))

  const state = EditorState.create({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      languageExtension(props.path),
      themeCompartment.of(currentThemeExtensions()),
      EditorState.readOnly.of(props.readOnly),
      EditorView.editable.of(!props.readOnly),
      saveKeymap,
      EditorView.updateListener.of((update) => {
        if (update.docChanged && !applyingExternalValue) {
          emit('update:modelValue', update.state.doc.toString())
        }
      }),
    ],
  })
  viewRef.value = new EditorView({ state, parent: hostRef.value })
}

function refreshTheme() {
  if (!viewRef.value) return
  viewRef.value.dispatch({
    effects: themeCompartment.reconfigure(currentThemeExtensions()),
  })
}

function insertText(text) {
  const view = viewRef.value
  if (!view) throw new Error('Lua 编辑器尚未就绪')
  const changes = view.state.changeByRange((range) => ({
    changes: { from: range.from, to: range.to, insert: String(text || '') },
    range: { from: range.from + String(text || '').length, to: range.from + String(text || '').length },
  }))
  view.dispatch(changes)
  view.focus()
}

defineExpose({ insertText })

watch(() => props.modelValue, (value) => {
  const view = viewRef.value
  if (!view || value === view.state.doc.toString()) return
  applyingExternalValue = true
  try {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
  } finally {
    applyingExternalValue = false
  }
})

onMounted(() => {
  createEditor()
  state.textCodeEditor.value = { insertText }
  themeObserver = new MutationObserver(refreshTheme)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  if (state.textCodeEditor.value?.insertText === insertText) state.textCodeEditor.value = null
  viewRef.value?.destroy()
  viewRef.value = null
})
</script>

<template>
  <div ref="hostRef" class="text-code-editor" />
</template>

<style scoped>
.text-code-editor {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.text-code-editor :deep(.cm-editor) {
  height: 100%;
}
</style>
