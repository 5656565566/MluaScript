import { replaceBlocklyWorkspace } from './blocklyWorkspace'
import { buildEditorSessionPayload, rememberEditorSessionSnapshot } from './editorSession'
import { createSaveCoordinator } from './saveCoordinator'

function replaceFilenameInPath(path, filename) {
  const normalizedPath = String(path || '').replace(/\\/g, '/')
  const normalizedFilename = String(filename || '')
  if (!normalizedPath) return normalizedFilename
  const parts = normalizedPath.split('/')
  parts[parts.length - 1] = normalizedFilename
  return parts.filter((part, index) => part || index === 0).join('/')
}

export function createEditorActions({
  state,
  editorApi,
  workspaceToLua,
  workspaceToXml,
  collectBlocklyDiagnostics = () => [],
  scheduler,
  getActions,
}) {
  const blocklySaves = createSaveCoordinator()

  function assertBlocklyLuaReady() {
    const workspace = state.blocklyEditor.value
    const diagnostics = collectBlocklyDiagnostics(workspace)
    const generationError = String(state.blocklyGenerationError?.value || '').trim()
    if (!diagnostics.length && !generationError) return
    const first = diagnostics[0] || { blockId: '', message: generationError }
    if (first.blockId) {
      workspace?.centerOnBlock?.(first.blockId)
      workspace?.getBlockById?.(first.blockId)?.select?.()
    }
    // 生成错误通常与首个积木诊断是同一问题，不重复计数。
    const errorCount = diagnostics.length || 1
    throw new Error(`Blockly 存在 ${errorCount} 个错误：${first.message}`)
  }

  async function applyBlocklyXmlToEditor() {
    if (!state.blocklyEditor.value) return
    state.suppressBlocklyAutosave.value = true
    try {
      await replaceBlocklyWorkspace(state.blocklyEditor.value, state.blocklyXml.value)
    } finally {
      scheduler.setTimeout(() => {
        state.suppressBlocklyAutosave.value = false
      }, 100)
    }
  }

  return {
    invalidateEditorOperations() {
      blocklySaves.beginDocumentTransition()
    },

    async applyHydratedBlocklyWorkspace() {
      await applyBlocklyXmlToEditor()
    },

    rebuildLuaCode() {
      if (!state.blocklyEditor.value) return
      try {
        state.blocklyXml.value = workspaceToXml(state.blocklyEditor.value)
        state.luaCode.value = workspaceToLua(state.blocklyEditor.value)
        state.blocklyGenerationError.value = ''
      } catch (error) {
        const message = error?.message || '生成 Lua 代码失败'
        state.blocklyGenerationError.value = message
        state.luaCode.value = `-- ${message}`
      }
    },

    async syncWorkspace() {
      if (!state.blocklyEditor.value || !state.editorSessionHydrated.value) return
      getActions().rebuildLuaCode()
      const payload = buildEditorSessionPayload(state)
      await editorApi.syncSession(payload)
      rememberEditorSessionSnapshot(state, payload)
    },

    async saveLuaScript() {
      const actions = getActions()
      actions.rebuildLuaCode()
      assertBlocklyLuaReady()
      const currentFilename = state.filename.value || 'script.lua'
      const previousPath = state.savePath.value || ''
      const savedPathFilename = previousPath ? previousPath.split('/').pop() : ''
      const hasPersistedFile = state.luaSaveMode.value === 'update' && Boolean(previousPath)
      const filenameChanged = hasPersistedFile && savedPathFilename && savedPathFilename !== currentFilename
      const effectivePath = filenameChanged
        ? replaceFilenameInPath(previousPath, currentFilename)
        : (previousPath || currentFilename)
      const payload = {
        path: effectivePath,
        content: state.luaCode.value,
        expectedMtime: state.luaDocumentMtime.value,
        previousPath: filenameChanged ? previousPath : null,
      }
      // “保存”是幂等写入：已有文件更新，文件被外部删除后则由后端重建。
      // 显式新建文件仍使用 createLuaFile，并继续保留重名保护。
      const data = await editorApi.updateLuaFile(payload)

      state.filename.value = data.filename || state.filename.value
      state.savePath.value = data.path || state.savePath.value
      state.luaDocumentMtime.value = data.mtime ?? null
      state.luaSaveMode.value = 'update'
      await actions.syncWorkspace()
      await actions.loadLuaFiles()
      actions.setStatus(`Lua 文件已保存到 ${state.savePath.value}`, 'success')
    },

    async runCurrentBlocklyLua() {
      const actions = getActions()
      actions.rebuildLuaCode()
      assertBlocklyLuaReady()
      return await actions.runLuaScript(null, state.luaCode.value)
    },

    async saveBlocklyWorkspace(showStatus = true) {
      if (!state.editorSessionHydrated.value) return null
      const actions = getActions()
      actions.rebuildLuaCode()
      const documentGeneration = blocklySaves.currentGeneration()
      const currentFilename = state.blocklyFilename.value || 'blockly.xml'
      const previousPath = state.blocklySavePath.value || ''
      const savedPathFilename = previousPath ? previousPath.split('/').pop() : ''
      const hasPersistedFile = state.blocklySaveMode.value === 'update' && Boolean(previousPath)
      const filenameChanged = hasPersistedFile && savedPathFilename && savedPathFilename !== currentFilename
      const effectivePath = filenameChanged
        ? replaceFilenameInPath(previousPath, currentFilename)
        : (previousPath || currentFilename)
      const payload = {
        path: effectivePath,
        xml: state.blocklyXml.value,
        expectedMtime: state.blocklyDocumentMtime.value,
        previousPath: filenameChanged ? previousPath : null,
      }
      return await blocklySaves.enqueue({
        documentGeneration,
        execute: async () => hasPersistedFile
          ? await editorApi.updateBlocklyFile(payload)
          : await editorApi.createBlocklyFile({ path: payload.path, xml: payload.xml }),
        commit: async (data) => {
          state.blocklyFilename.value = data.filename || state.blocklyFilename.value
          state.blocklySavePath.value = data.path || state.blocklySavePath.value
          state.blocklySaveDir.value = data.path || state.blocklySaveDir.value
          state.blocklyDocumentMtime.value = data.mtime ?? null
          state.blocklySaveMode.value = 'update'
          state.lastSavedBlocklyXml.value = payload.xml
          await actions.syncWorkspace()
          await actions.reloadBlocklyFiles()
          if (showStatus) actions.setStatus(`Blockly 已保存到 ${state.blocklySavePath.value}`, 'success')
        },
      })
    },

    async loadBlocklyWorkspace(filename) {
      const actions = getActions()
      const documentGeneration = blocklySaves.beginDocumentTransition()
      return await blocklySaves.enqueue({
        documentGeneration,
        execute: async () => await editorApi.loadBlocklyFile(filename),
        commit: async (data) => {
          state.blocklyFilename.value = data.filename || filename
          state.blocklySavePath.value = data.path || filename
          state.blocklyXml.value = data.xml || ''
          state.blocklyDocumentMtime.value = data.mtime ?? null
          state.blocklySaveMode.value = data.saveMode || 'update'
          state.lastSavedBlocklyXml.value = state.blocklyXml.value
          actions.setStatus(`已加载 Blockly XML: ${state.blocklyFilename.value}`)
          if (!state.blocklyEditor.value) return
          await applyBlocklyXmlToEditor()
          actions.rebuildLuaCode()
          await actions.syncWorkspace()
        },
      })
    },

    async createNewBlocklyWorkspace(path) {
      const actions = getActions()
      const documentGeneration = blocklySaves.beginDocumentTransition()
      const xml = state.blocklyXml.value || '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
      return await blocklySaves.enqueue({
        documentGeneration,
        execute: async () => await editorApi.createBlocklyFile({ path, xml }),
        commit: async (data) => {
          state.blocklyFilename.value = data.filename || state.blocklyFilename.value
          state.blocklySavePath.value = data.path || state.blocklySavePath.value
          state.blocklyDocumentMtime.value = data.mtime ?? null
          state.blocklySaveMode.value = 'update'
          state.lastSavedBlocklyXml.value = xml
          await actions.syncWorkspace()
          await actions.reloadBlocklyFiles()
          actions.setStatus(`已创建 Blockly 文件: ${state.blocklyFilename.value}`, 'success')
        },
      })
    },

    async validateBlocklyName(path) {
      return await editorApi.validateBlocklyName(path)
    },

    async reloadBlocklyFiles() {
      const data = await editorApi.listBlocklyFiles()
      state.blocklyFiles.value = data.items || []
    },

    async loadLuaFile(path) {
      const data = await editorApi.loadLuaFile(path)
      state.filename.value = data.filename || path
      state.savePath.value = data.path || path
      state.luaCode.value = data.content || ''
      state.luaDocumentMtime.value = data.mtime ?? null
      state.luaSaveMode.value = data.saveMode || 'update'
      await getActions().syncWorkspace()
      getActions().setStatus(`已加载 Lua 文件: ${state.filename.value}`)
    },

    async createNewLuaFile(path) {
      const actions = getActions()
      actions.rebuildLuaCode()
      assertBlocklyLuaReady()
      const data = await editorApi.createLuaFile({ path, content: state.luaCode.value })
      state.filename.value = data.filename || state.filename.value
      state.savePath.value = data.path || state.savePath.value
      state.luaDocumentMtime.value = data.mtime ?? null
      state.luaSaveMode.value = 'update'
      await actions.syncWorkspace()
      actions.setStatus(`已创建 Lua 文件: ${state.filename.value}`, 'success')
      return data
    },

    async validateLuaName(path) {
      return await editorApi.validateLuaName(path)
    },

    async loadLuaFiles() {
      const data = await editorApi.listLuaFiles()
      state.luaFiles.value = data.items || []
    },
  }
}
