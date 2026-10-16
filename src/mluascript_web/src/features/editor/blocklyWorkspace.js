import { loadBlocklyXml } from '../../blockly/xmlImport.js'

export async function replaceBlocklyWorkspace(editor, xml) {
  if (!editor) return
  const { Events } = await import('blockly')
  Events.disable()
  try {
    editor.clear()
    if (xml) {
      loadBlocklyXml(xml, editor)
    }
  } finally {
    Events.enable()
  }

  // Blockly-dependent fields rebuild their labels after this lifecycle event.
  Events.fire(new Events.FinishedLoading(editor))
}

