import * as Blockly from 'blockly'
import { migrateLegacyProjectModuleCallXml } from './projectModuleCall.js'

const blockTags = new Set(['block', 'shadow'])
const inputTags = new Set(['xml', 'value', 'statement', 'next'])

export function loadBlocklyXml(xmlText, workspace) {
  const dom = Blockly.utils.xml.textToDom(String(xmlText || ''))
  const removedTypes = new Map()
  const isUnknown = (element) => !Object.hasOwn(Blockly.Blocks, element.getAttribute('type') || '')

  function recordRemoved(element) {
    const tag = element.nodeName.toLowerCase()
    if (blockTags.has(tag) && isUnknown(element)) {
      const type = element.getAttribute('type') || '缺少 type'
      removedTypes.set(type, (removedTypes.get(type) || 0) + 1)
    }
    if (blockTags.has(tag) || inputTags.has(tag)) {
      for (const child of [...element.children]) recordRemoved(child)
    }
  }

  function prune(element) {
    const tag = element.nodeName.toLowerCase()
    if (blockTags.has(tag) && isUnknown(element)) {
      const parent = element.parentNode
      const next = [...element.children].find(child => child.nodeName.toLowerCase() === 'next')
      const continuation = [...(next?.children || [])].find(child => blockTags.has(child.nodeName.toLowerCase()))
      if (continuation) {
        if (parent.nodeName.toLowerCase() === 'xml') {
          for (const position of ['x', 'y']) {
            if (element.hasAttribute(position)) continuation.setAttribute(position, element.getAttribute(position))
          }
        }
        // 先移出后续语句，再统计丢弃子树，避免把保留的流程计入删除数量。
        parent.replaceChild(continuation, element)
      } else {
        parent.removeChild(element)
      }
      recordRemoved(element)
      if (continuation) prune(continuation)
      return
    }
    if (blockTags.has(tag) || inputTags.has(tag)) {
      for (const child of [...element.children]) prune(child)
    }
  }

  prune(dom)
  migrateLegacyProjectModuleCallXml(dom)
  Blockly.Xml.domToWorkspace(dom, workspace)
  if (removedTypes.size) {
    const count = [...removedTypes.values()].reduce((total, value) => total + value, 0)
    const types = [...removedTypes].map(([type, total]) => `${type} × ${total}`).join('、')
    const message = `已删除 ${count} 个不支持的积木（${types}）及其输入子块，已保留后续语句。请检查剩余流程。`
    console.warn(message)
    globalThis.window?.$message?.warning(message, { duration: 10000 })
  }
}
