export async function replaceBlocklyWorkspace(editor, xml) {
  if (!editor) return
  const { utils, Xml, Events } = await import('blockly')
  Events.disable()
  try {
    editor.clear()
    if (xml) {
      const dom = utils.xml.textToDom(xml)
      Xml.domToWorkspace(dom, editor)
    }
  } finally {
    Events.enable()
  }

  // Blockly-dependent fields rebuild their labels after this lifecycle event.
  Events.fire(new Events.FinishedLoading(editor))
}

