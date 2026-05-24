import { luaOrder, MAA_RESULT_TYPE, MAA_ITEMS_TYPE, MAA_ITEM_TYPE, MAA_BOX_TYPE, MAA_ROI_TYPE } from '../constants'

export const visionBlocks = [
  {
    type: 'maa_roi_rect',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '在这里找 左边距 %1 上边距 %2 区域宽 %3 区域高 %4',
      args0: [
        { type: 'input_value', name: 'X', check: 'Number' },
        { type: 'input_value', name: 'Y', check: 'Number' },
        { type: 'input_value', name: 'W', check: 'Number' },
        { type: 'input_value', name: 'H', check: 'Number' },
      ],
      output: MAA_ROI_TYPE,
      tooltip: '从屏幕左上角开始，指定一块查找范围。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x = generator.valueToCode(block, 'X', luaOrder) || '0'
      const y = generator.valueToCode(block, 'Y', luaOrder) || '0'
      const w = generator.valueToCode(block, 'W', luaOrder) || '0'
      const h = generator.valueToCode(block, 'H', luaOrder) || '0'
      return [`{${x}, ${y}, ${w}, ${h}}`, luaOrder]
    },
  },
  {
    type: 'maa_roi_fullscreen',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '全屏范围',
      output: MAA_ROI_TYPE,
      tooltip: '不限制区域，直接全屏识别。',
      helpUrl: '',
    },
    generator() {
      return ['nil', luaOrder]
    },
  },
  {
    type: 'maa_default_threshold',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '常用阈值 %1',
      args0: [{
        type: 'field_dropdown',
        name: 'VALUE',
        options: [
          ['默认', '0'],
          ['宽松 0.75', '0.75'],
          ['常用 0.80', '0.80'],
          ['严格 0.90', '0.90'],
        ],
      }],
      output: 'Number',
      tooltip: '模板匹配常用阈值预设。',
      helpUrl: '',
    },
    generator(block) {
      return [block.getFieldValue('VALUE') || '0', luaOrder]
    },
  },
  {
    type: 'maa_find_ocr',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '文字识别(首个) 包含文本 %1 区域 %2 图片(可选) %3',
      args0: [
        { type: 'input_value', name: 'EXPECTED', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '执行 OCR 识别，返回命中期望文本的首个结果集对象',
      helpUrl: '',
    },
    generator(block, generator) {
      const expected = generator.valueToCode(block, 'EXPECTED', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_ocr('OCR', ${expected}, ${roi}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_find_all_ocr',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '文字识别(全量) 包含文本 %1 区域 %2 图片(可选) %3',
      args0: [
        { type: 'input_value', name: 'EXPECTED', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '执行全量 OCR 识别，返回命中期望文本的结果集对象',
      helpUrl: '',
    },
    generator(block, generator) {
      const expected = generator.valueToCode(block, 'EXPECTED', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_all_ocr('OCR', ${expected}, ${roi}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_find_text_in_items',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '在结果中查找包含文字 列表 %1 文本 %2',
      args0: [
        { type: 'input_value', name: 'ITEMS', check: MAA_ITEMS_TYPE },
        { type: 'input_value', name: 'TEXT', check: 'String' },
      ],
      output: MAA_ITEM_TYPE,
      tooltip: '遍历 items 列表，返回第一个 text 包含指定文本的项。未找到则返回 nil。',
      helpUrl: '',
    },
    generator(block, generator) {
      const items = generator.valueToCode(block, 'ITEMS', luaOrder) || '{}'
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`find_text_in_items(${items}, ${text})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_find_text_in_items_fuzzy',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '模糊查找包含文字(拼接) 列表 %1 文本 %2',
      args0: [
        { type: 'input_value', name: 'ITEMS', check: MAA_ITEMS_TYPE },
        { type: 'input_value', name: 'TEXT', check: 'String' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '将所有文字拼接后判断是否包含指定文本。',
      helpUrl: '',
    },
    generator(block, generator) {
      const items = generator.valueToCode(block, 'ITEMS', luaOrder) || '{}'
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`find_text_in_items_fuzzy(${items}, ${text})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_is_text_in_items',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '结果中包含文字? 列表 %1 文本 %2',
      args0: [
        { type: 'input_value', name: 'ITEMS', check: MAA_ITEMS_TYPE },
        { type: 'input_value', name: 'TEXT', check: 'String' },
      ],
      output: 'Boolean',
      tooltip: '判断结果列表中是否包含指定文本。',
      helpUrl: '',
    },
    generator(block, generator) {
      const items = generator.valueToCode(block, 'ITEMS', luaOrder) || '{}'
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`result_contains_text(${items}, ${text})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_is_text_in_items_fuzzy',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '模糊包含文字?(拼接) 列表 %1 文本 %2',
      args0: [
        { type: 'input_value', name: 'ITEMS', check: MAA_ITEMS_TYPE },
        { type: 'input_value', name: 'TEXT', check: 'String' },
      ],
      output: 'Boolean',
      tooltip: '判断所有文字拼接后是否包含指定文本。',
      helpUrl: '',
    },
    generator(block, generator) {
      const items = generator.valueToCode(block, 'ITEMS', luaOrder) || '{}'
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`result_contains_text_fuzzy(${items}, ${text})`, luaOrder]
    },
  },
  {
    type: 'maa_find_template',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '模板匹配 模板 %1 区域 %2 阈值 %3 图片(可选) %4',
      args0: [
        { type: 'input_value', name: 'TEMPLATE', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'THRESHOLD', check: 'Number' },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '模板匹配，返回统一的结果集对象',
      helpUrl: '',
    },
    generator(block, generator) {
      const template = generator.valueToCode(block, 'TEMPLATE', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const threshold = generator.valueToCode(block, 'THRESHOLD', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_template('TemplateMatch', ${template}, ${roi}, ${threshold}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_find_nnd',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '神经网络检测(NND) 模型 %1 目标 %2 区域 %3 图片(可选) %4',
      args0: [
        { type: 'input_value', name: 'MODEL', check: 'String' },
        { type: 'input_value', name: 'TARGETS', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '按模型名和目标名执行 NND 识别，目标可用 | 分隔多个。',
      helpUrl: '',
    },
    generator(block, generator) {
      const model = generator.valueToCode(block, 'MODEL', luaOrder) || "''"
      const targets = generator.valueToCode(block, 'TARGETS', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_nnd('NND', ${model}, ${targets}, ${roi}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_find_feature',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '特征匹配 模板 %1 区域 %2 图片(可选) %3',
      args0: [
        { type: 'input_value', name: 'TEMPLATE', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '特征匹配识别',
      helpUrl: '',
    },
    generator(block, generator) {
      const template = generator.valueToCode(block, 'TEMPLATE', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_feature('FeatureMatch', ${template}, ${roi}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_find_color',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '颜色匹配 颜色下界 %1 颜色上界 %2 区域 %3 图片(可选) %4',
      args0: [
        { type: 'input_value', name: 'LOWER', check: 'String' },
        { type: 'input_value', name: 'UPPER', check: 'String' },
        { type: 'input_value', name: 'ROI', check: MAA_ROI_TYPE },
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: MAA_RESULT_TYPE,
      tooltip: '颜色匹配识别',
      helpUrl: '',
    },
    generator(block, generator) {
      const lower = generator.valueToCode(block, 'LOWER', luaOrder) || 'nil'
      const upper = generator.valueToCode(block, 'UPPER', luaOrder) || 'nil'
      const roi = generator.valueToCode(block, 'ROI', luaOrder) || 'nil'
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`maa.find_color('ColorMatch', ${lower}, ${upper}, ${roi}, ${image})`, luaOrder]
    },
  },
  {
    type: 'maa_color_hex',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '颜色 %1',
      args0: [{ type: 'field_input', name: 'COLOR', text: '#FF0000' }],
      output: 'String',
      tooltip: '输入十六进制颜色，例如 #FF0000。',
      helpUrl: '',
    },
    generator(block) {
      const color = block.getFieldValue('COLOR') || '#FF0000'
      return [`'${color}'`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_items',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取结果列表 对象 %1',
      args0: [{ type: 'input_value', name: 'RESULT', check: MAA_RESULT_TYPE }],
      output: MAA_ITEMS_TYPE,
      tooltip: '读取 result.items 字段',
      helpUrl: '',
    },
    generator(block, generator) {
      const result = generator.valueToCode(block, 'RESULT', luaOrder) || '{}'
      return [`result_items(${result})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_count',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取结果数量 对象 %1',
      args0: [{ type: 'input_value', name: 'RESULT', check: MAA_RESULT_TYPE }],
      output: 'Number',
      tooltip: '读取 #result.items',
      helpUrl: '',
    },
    generator(block, generator) {
      const result = generator.valueToCode(block, 'RESULT', luaOrder) || '{}'
      return [`result_count(${result})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_first_item',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取第一个结果 列表 %1',
      args0: [{ type: 'input_value', name: 'ITEMS', check: MAA_ITEMS_TYPE }],
      output: MAA_ITEM_TYPE,
      tooltip: '读取 items[1]',
      helpUrl: '',
    },
    generator(block, generator) {
      const items = generator.valueToCode(block, 'ITEMS', luaOrder) || '{}'
      return [`(result_first(${items}) or {})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_item_text',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取结果文本 项 %1',
      args0: [{ type: 'input_value', name: 'ITEM', check: MAA_ITEM_TYPE }],
      output: 'String',
      tooltip: '读取 item.text',
      helpUrl: '',
    },
    generator(block, generator) {
      const item = generator.valueToCode(block, 'ITEM', luaOrder) || '{}'
      return [`item_text(${item})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_item_box',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取结果框 项 %1',
      args0: [{ type: 'input_value', name: 'ITEM', check: MAA_ITEM_TYPE }],
      output: MAA_BOX_TYPE,
      tooltip: '读取 item.box',
      helpUrl: '',
    },
    generator(block, generator) {
      const item = generator.valueToCode(block, 'ITEM', luaOrder) || '{}'
      return [`(item_box(${item}) or {})`, luaOrder]
    },
  },
  {
    type: 'maa_easy_get_item_score',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '获取结果分数 项 %1',
      args0: [{ type: 'input_value', name: 'ITEM', check: MAA_ITEM_TYPE }],
      output: 'Number',
      tooltip: '读取 item.score',
      helpUrl: '',
    },
    generator(block, generator) {
      const item = generator.valueToCode(block, 'ITEM', luaOrder) || '{}'
      return [`item_score(${item})`, luaOrder]
    },
  },
  {
    type: 'maa_click_result',
    category: '快捷识别',
    colour: '#ef4444',
    definition: {
      message0: '点击结果 %1 偏移X %2 偏移Y %3',
      args0: [
        { type: 'input_value', name: 'RESULT', check: [MAA_RESULT_TYPE, MAA_ITEM_TYPE] },
        { type: 'input_value', name: 'OFFSET_X', check: 'Number' },
        { type: 'input_value', name: 'OFFSET_Y', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '只使用一次识别结果。默认轻微上移点击，减少遮挡与误触。',
      helpUrl: '',
    },
    generator(block, generator) {
      const result = generator.valueToCode(block, 'RESULT', luaOrder) || '{}'
      const offsetX = generator.valueToCode(block, 'OFFSET_X', luaOrder) || '0'
      const offsetY = generator.valueToCode(block, 'OFFSET_Y', luaOrder) || '-5'
      return `click_result(${result}, ${offsetX}, ${offsetY})\n`
    },
  },
]
