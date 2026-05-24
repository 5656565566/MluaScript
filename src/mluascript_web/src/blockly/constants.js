import * as Blockly from 'blockly'
import { luaGenerator } from 'blockly/lua'

export const MAA_RESULT_TYPE = 'Result'
export const MAA_ITEMS_TYPE = 'Items'
export const MAA_ITEM_TYPE = 'Item'
export const MAA_BOX_TYPE = 'Box'
export const MAA_ROI_TYPE = 'Roi'

export const luaOrder = luaGenerator.ORDER_ATOMIC || 0

export const PICKER_ICON_TYPE = new Blockly.icons.IconType('lua_picker')
