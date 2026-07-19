import * as Blockly from 'blockly'
import { PICKER_ICON_TYPE } from './constants'
import {
  openBlocklyPickerForBlock,
  openSharedVariablePickerForBlock,
  createSharedVariableDropdownOptions,
  isSharedVariableCommandValue,
  handleSharedVariableCommand
} from './utils'
import { createVariableDropdownOptions, getVariableFieldLabel, handleVariableCommand, isVariableCommandValue, openVariablePickerForBlock } from './variableContext'

const OriginalFieldDropdown = Blockly.FieldDropdown

export class LuaVariableField extends OriginalFieldDropdown {
  constructor(menuGenerator, config = {}) {
    const variableConfig = {
      fieldName: config.fieldName || 'VAR',
      includeGlobals: config.includeGlobals !== false,
      includeLocals: Boolean(config.includeLocals),
      includeArguments: Boolean(config.includeArguments),
      includeRename: Boolean(config.includeRename),
      includeDelete: Boolean(config.includeDelete),
      title: config.title || '选择变量',
      emptyText: config.emptyText || '当前范围内没有可选变量',
      defaultLabel: config.defaultLabel || '选择变量…',
      forcePicker: Boolean(config.forcePicker),
    }
    const generator = typeof menuGenerator === 'function'
      ? menuGenerator
      : function() {
          return createVariableDropdownOptions(this.getSourceBlock(), {
            ...this.variableConfig_,
          })
        }
    super(generator)
    this.variableConfig_ = variableConfig
  }

  doClassValidation_(newValue) {
    if (isVariableCommandValue(newValue)) {
      return this.getValue() || null
    }
    return newValue
  }

  getOptions(useCache) {
    this.menuGenerator_ = () => createVariableDropdownOptions(this.getSourceBlock(), {
      ...this.variableConfig_,
    })
    return super.getOptions(useCache)
  }

  doValueUpdate_(newValue) {
    if (isVariableCommandValue(newValue)) {
      const block = this.getSourceBlock()
      handleVariableCommand(block, newValue, this.variableConfig_)
      this.forceRerender?.()
      return
    }
    super.doValueUpdate_(newValue)
    this.forceRerender?.()
  }

  onItemSelected_(menu, menuItem) {
    const value = menuItem.getValue()
    if (isVariableCommandValue(value)) {
      handleVariableCommand(this.getSourceBlock(), value, this.variableConfig_)
      this.forceRerender?.()
      return
    }
    super.onItemSelected_(menu, menuItem)
    this.forceRerender?.()
  }

  getText() {
    return getVariableFieldLabel(this.getSourceBlock(), this.getValue(), this.variableConfig_)
  }

  getText_() {
    return this.getText()
  }

  showEditor_(e) {
    const block = this.getSourceBlock()
    if (this.variableConfig_.forcePicker) {
      openVariablePickerForBlock(block, this.variableConfig_.fieldName, this.variableConfig_)
      return
    }
    super.showEditor_(e)
  }
}

export class SharedVariableField extends OriginalFieldDropdown {
  constructor(value = '', config = {}) {
    const normalizedConfig = config && typeof config === 'object' ? config : {}
    const sharedVariableConfig = {
      fieldName: normalizedConfig.fieldName || 'VAR_NAME',
      title: normalizedConfig.title || '选择全局状态',
      defaultLabel: normalizedConfig.defaultLabel || '选择全局状态…',
    }
    const generator = function() {
      return createSharedVariableDropdownOptions(this.getSourceBlock(), sharedVariableConfig)
    }
    super(generator)
    this.sharedVariableConfig_ = sharedVariableConfig
    this.setValue(String(value || '').trim())
  }

  static fromJson(options) {
    return new SharedVariableField(options['text'], options)
  }

  initView(...args) {
    super.initView(...args)
    this.textElement_?.classList?.add('shared-variable-text')
    this.fieldGroup_?.classList?.add('shared-variable-field')
  }

  doClassValidation_(newValue) {
    if (isSharedVariableCommandValue(newValue)) {
      return this.getValue() || null
    }
    return newValue
  }

  getOptions(useCache) {
    this.menuGenerator_ = () => createSharedVariableDropdownOptions(this.getSourceBlock(), this.sharedVariableConfig_)
    return super.getOptions(useCache)
  }

  doValueUpdate_(newValue) {
    if (isSharedVariableCommandValue(newValue)) {
      const block = this.getSourceBlock()
      handleSharedVariableCommand(block, newValue, this.sharedVariableConfig_)
      this.forceRerender?.()
      return
    }
    super.doValueUpdate_(newValue)
    this.forceRerender?.()
  }

  onItemSelected_(menu, menuItem) {
    const value = menuItem.getValue()
    if (isSharedVariableCommandValue(value)) {
      handleSharedVariableCommand(this.getSourceBlock(), value, this.sharedVariableConfig_)
      this.forceRerender?.()
      return
    }
    super.onItemSelected_(menu, menuItem)
    this.forceRerender?.()
  }

  getText() {
    const defaultLabel = this.sharedVariableConfig_ ? this.sharedVariableConfig_.defaultLabel : '选择全局状态…'
    return this.getValue() || defaultLabel
  }

  getText_() {
    return this.getText()
  }
}

export class MaaPickerIcon extends Blockly.icons.Icon {
  constructor(sourceBlock, getConfig) {
    super(sourceBlock)
    this.getConfig_ = getConfig
  }

  getType() {
    return PICKER_ICON_TYPE
  }

  initView(pointerdownListener) {
    super.initView(pointerdownListener)
    if (!this.svgRoot) return
    Blockly.utils.dom.addClass(this.svgRoot, 'picker-icon')

    while (this.svgRoot.firstChild) {
      this.svgRoot.removeChild(this.svgRoot.firstChild)
    }

    Blockly.utils.dom.createSvgElement('rect', {
      class: 'blocklyIconShape',
      rx: '4',
      ry: '4',
      height: '16',
      width: '16',
      fill: '#995ba5',
      stroke: '#fff',
      'stroke-width': '1px'
    }, this.svgRoot)
    Blockly.utils.dom.createSvgElement('path', {
      class: 'blocklyIconSymbol',
      d: 'm4.203,7.296 0,1.368 -0.92,0.677 -0.11,0.41 0.9,1.559 0.41,0.11 1.043,-0.457 1.187,0.683 0.127,1.134 0.3,0.3 1.8,0 0.3,-0.299 0.127,-1.138 1.185,-0.682 1.046,0.458 0.409,-0.11 0.9,-1.559 -0.11,-0.41 -0.92,-0.677 0,-1.366 0.92,-0.677 0.11,-0.41 -0.9,-1.559 -0.409,-0.109 -1.046,0.458 -1.185,-0.682 -0.127,-1.138 -0.3,-0.299 -1.8,0 -0.3,0.3 -0.126,1.135 -1.187,0.682 -1.043,-0.457 -0.41,0.11 -0.899,1.559 0.108,0.409z',
      fill: '#fff'
    }, this.svgRoot)
    Blockly.utils.dom.createSvgElement('circle', {
      class: 'blocklyIconShape',
      r: '2.7',
      cx: '8',
      cy: '8',
      fill: '#995ba5',
      stroke: '#fff',
      'stroke-width': '1px'
    }, this.svgRoot)
  }

  getWeight() {
    return 60
  }

  getSize() {
    return new Blockly.utils.Size(17, 17)
  }

  onClick() {
    super.onClick()
    const config = this.getConfig_ ? this.getConfig_() : null
    if (!config) return
    setTimeout(() => {
      openBlocklyPickerForBlock(this.sourceBlock, config)
    }, 0)
  }

  applyColour() {}
  updateEditable() {}
}

export function registerCustomFields() {
  Blockly.fieldRegistry.register('field_variable_custom', LuaVariableField)
  Blockly.fieldRegistry.register('field_shared_variable', SharedVariableField)
}
