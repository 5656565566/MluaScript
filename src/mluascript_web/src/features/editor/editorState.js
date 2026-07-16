import { ref, shallowRef } from 'vue'

export function createEditorState() {
  return {
    blocklyEditorRef: ref(null),
    blocklyEditor: shallowRef(null),
    suppressBlocklyAutosave: ref(false),
    editorSessionHydrated: ref(false),
    lastSavedBlocklyXml: ref(''),
    lastSessionBlocklyXml: ref(''),
    lastSessionBlocklyFilename: ref(''),
    lastSessionBlocklyPath: ref(''),
    lastSessionLuaCode: ref(''),
    lastSessionLuaFilename: ref(''),
    lastSessionLuaPath: ref(''),
    luaCode: ref('-- 请先编排 Blockly 拼图块'),
    filename: ref('script.lua'),
    blocklyFilename: ref('blockly.xml'),
    savePath: ref(''),
    blocklySavePath: ref(''),
    blocklySaveDir: ref(''),
    blocklyXml: ref(''),
    blocklyDocumentMtime: ref(null),
    luaDocumentMtime: ref(null),
    blocklySaveMode: ref('create'),
    luaSaveMode: ref('create'),
    blocklyWorkspaceManagerModalId: ref(null),
  }
}
