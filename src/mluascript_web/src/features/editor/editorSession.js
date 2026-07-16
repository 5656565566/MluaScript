function asString(value, fallback = '') {
  return String(value ?? fallback)
}

export function rememberEditorSessionSnapshot(state, editorSession = {}) {
  const blocklyDocument = editorSession.blocklyDocument || {}
  const luaDocument = editorSession.luaDocument || {}
  state.lastSessionBlocklyXml.value = asString(blocklyDocument.xml)
  state.lastSessionBlocklyFilename.value = asString(blocklyDocument.filename)
  state.lastSessionBlocklyPath.value = asString(blocklyDocument.path)
  state.lastSessionLuaCode.value = asString(luaDocument.content)
  state.lastSessionLuaFilename.value = asString(luaDocument.filename)
  state.lastSessionLuaPath.value = asString(luaDocument.path)
  state.editorSessionHydrated.value = true
}

export function hasUnsyncedBlocklyDraft(state) {
  return (
    state.blocklyXml.value !== state.lastSessionBlocklyXml.value
    || state.blocklyFilename.value !== state.lastSessionBlocklyFilename.value
    || state.blocklySavePath.value !== state.lastSessionBlocklyPath.value
  )
}

export function hasUnsyncedLuaDraft(state) {
  return (
    state.luaCode.value !== state.lastSessionLuaCode.value
    || state.filename.value !== state.lastSessionLuaFilename.value
    || state.savePath.value !== state.lastSessionLuaPath.value
  )
}

export function applyEditorSession(state, editorSession = {}) {
  const blocklyDocument = editorSession.blocklyDocument || {}
  const luaDocument = editorSession.luaDocument || {}
  const shouldApplyBlockly = !state.editorSessionHydrated.value || !hasUnsyncedBlocklyDraft(state)
  const shouldApplyLua = !state.editorSessionHydrated.value || !hasUnsyncedLuaDraft(state)

  if (shouldApplyBlockly) {
    state.blocklyXml.value = asString(blocklyDocument.xml)
    state.lastSavedBlocklyXml.value = asString(blocklyDocument.xml)
    state.blocklyFilename.value = asString(blocklyDocument.filename, state.blocklyFilename.value || 'blockly.xml')
    state.blocklySavePath.value = asString(blocklyDocument.path, state.blocklySavePath.value)
    state.blocklyDocumentMtime.value = blocklyDocument.mtime ?? null
    state.blocklySaveMode.value = asString(blocklyDocument.saveMode, state.blocklySaveMode.value || 'create')
  }

  if (shouldApplyLua) {
    state.luaCode.value = asString(luaDocument.content)
    state.filename.value = asString(luaDocument.filename, state.filename.value || 'script.lua')
    state.savePath.value = asString(luaDocument.path, state.savePath.value)
    state.luaDocumentMtime.value = luaDocument.mtime ?? null
    state.luaSaveMode.value = asString(luaDocument.saveMode, state.luaSaveMode.value || 'create')
  }

  rememberEditorSessionSnapshot(state, editorSession)
  return { blocklyApplied: shouldApplyBlockly, luaApplied: shouldApplyLua }
}

export function buildEditorSessionPayload(state) {
  return {
    blocklyDocument: {
      xml: state.blocklyXml.value,
      filename: state.blocklyFilename.value,
      path: state.blocklySavePath.value,
      mtime: state.blocklyDocumentMtime.value,
      saveMode: state.blocklySaveMode.value,
      dirty: state.blocklyXml.value !== state.lastSavedBlocklyXml.value,
    },
    luaDocument: {
      content: state.luaCode.value,
      filename: state.filename.value,
      path: state.savePath.value,
      mtime: state.luaDocumentMtime.value,
      saveMode: state.luaSaveMode.value,
      dirty: hasUnsyncedLuaDraft(state),
    },
  }
}

