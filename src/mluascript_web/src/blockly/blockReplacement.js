import * as Blockly from 'blockly'

/**
 * 替换调用块时保留可兼容的参数连接与外围连接。
 * 语句块切换为值块时会先修复原语句链；值块切换为语句块时则安全脱离父输入。
 */
export function replaceCallableBlock(block, targetType, configure) {
  if (!block || block.isDisposed?.() || block.type === targetType) {
    if (block && typeof configure === 'function') configure(block)
    return block || null
  }

  const workspace = block.workspace || Blockly.getMainWorkspace()
  if (!workspace || typeof workspace.newBlock !== 'function') return null

  const xy = typeof block.getRelativeToSurfaceXY === 'function'
    ? block.getRelativeToSurfaceXY()
    : { x: block.x || 0, y: block.y || 0 }
  const outputTarget = block.outputConnection?.targetConnection || null
  const previousTarget = block.previousConnection?.targetConnection || null
  const nextTarget = block.nextConnection?.targetConnection || null
  const childTargets = new Map()
  for (const input of block.inputList || []) {
    const target = input.connection?.targetConnection
    if (input.name && target) childTargets.set(input.name, target)
  }

  // 子块需要在旧块销毁前断开，否则 Blockly 会连同输入树一起销毁。
  for (const target of childTargets.values()) target.disconnect?.()
  outputTarget?.disconnect?.()
  previousTarget?.disconnect?.()
  nextTarget?.disconnect?.()

  const newBlock = workspace.newBlock(targetType)
  newBlock.initSvg?.()
  if (typeof configure === 'function') configure(newBlock)
  newBlock.render?.()
  newBlock.moveBy?.(xy.x, xy.y)

  for (const [inputName, target] of childTargets) {
    const inputConnection = newBlock.getInput?.(inputName)?.connection
    if (inputConnection && !inputConnection.isConnected?.()) inputConnection.connect(target)
  }

  if (newBlock.outputConnection && outputTarget) {
    outputTarget.connect(newBlock.outputConnection)
  } else if (newBlock.previousConnection) {
    if (previousTarget) previousTarget.connect(newBlock.previousConnection)
    if (nextTarget && newBlock.nextConnection) newBlock.nextConnection.connect(nextTarget)
  } else if (previousTarget && nextTarget) {
    // 语句块变为值块后，原调用从语句链消失，但前后语句仍应保持相连。
    previousTarget.connect(nextTarget)
  }

  block.dispose(false)
  newBlock.select?.()
  return newBlock
}
