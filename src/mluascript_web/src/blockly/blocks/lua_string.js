import { luaOrder } from '../constants'

function createStringExpressionBlock({ type, label, args, output = 'String', tooltip, generatorCode }) {
  return {
    type,
    category: null,
    definition: {
      style: 'text_blocks',
      message0: label,
      args0: args,
      output,
      tooltip,
      helpUrl: '',
    },
    generator(block, generator) {
      return generatorCode(block, generator)
    },
  }
}

function createStringStatementBlock({ type, label, args, tooltip, generatorCode }) {
  return {
    type,
    category: null,
    definition: {
      style: 'text_blocks',
      message0: label,
      args0: args,
      previousStatement: null,
      nextStatement: null,
      tooltip,
      helpUrl: '',
    },
    generator(block, generator) {
      return generatorCode(block, generator)
    },
  }
}

export const luaStringBlocks = [
  createStringExpressionBlock({
    type: 'lua_string_byte',
    label: '字符码 字符串 %1 位置 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'INDEX', check: 'Number' },
    ],
    output: 'Number',
    tooltip: '调用 string.byte(s, i) 获取指定位置字符的 ASCII/字节码',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const index = generator.valueToCode(block, 'INDEX', luaOrder) || '1'
      return [`string.byte(${text}, ${index})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_char',
    label: '字符转文本 编码1 %1 编码2 %2',
    args: [
      { type: 'input_value', name: 'CODE1', check: 'Number' },
      { type: 'input_value', name: 'CODE2', check: 'Number' },
    ],
    tooltip: '调用 string.char(a, b) 将编码转换为字符',
    generatorCode(block, generator) {
      const code1 = generator.valueToCode(block, 'CODE1', luaOrder) || '65'
      const code2 = generator.valueToCode(block, 'CODE2', luaOrder) || '66'
      return [`string.char(${code1}, ${code2})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_dump',
    label: '序列化函数 %1',
    args: [
      { type: 'input_value', name: 'FUNC' },
    ],
    tooltip: '调用 string.dump(func) 序列化函数为二进制字符串',
    generatorCode(block, generator) {
      const func = generator.valueToCode(block, 'FUNC', luaOrder) || 'print'
      return [`string.dump(${func})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_find_start',
    label: '查找子串起始 文本 %1 查找 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.find(text, pattern) 并返回起始位置',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      return [`(string.find(${text}, ${pattern}))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_find_end',
    label: '查找子串结束 文本 %1 查找 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.find(text, pattern) 并返回结束位置',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      return [`(select(2, string.find(${text}, ${pattern})))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_format',
    label: '格式化文本 模板 %1 参数 %2',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
      { type: 'input_value', name: 'VALUE' },
    ],
    tooltip: '调用 string.format(fmt, value) 格式化字符串',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || "''"
      return [`string.format(${format}, ${value})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_gmatch',
    label: '模式迭代器 文本 %1 模式 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
    ],
    output: null,
    tooltip: '调用 string.gmatch(text, pattern) 返回迭代器',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      return [`string.gmatch(${text}, ${pattern})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_gsub_text',
    label: '全局替换结果 文本 %1 查找 %2 替换 %3',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
      { type: 'input_value', name: 'REPL', check: 'String' },
    ],
    tooltip: '调用 string.gsub(text, pattern, repl) 并返回替换后的文本',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      const repl = generator.valueToCode(block, 'REPL', luaOrder) || "''"
      return [`(string.gsub(${text}, ${pattern}, ${repl}))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_gsub_count',
    label: '全局替换次数 文本 %1 查找 %2 替换 %3',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
      { type: 'input_value', name: 'REPL', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.gsub(text, pattern, repl) 并返回替换次数',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      const repl = generator.valueToCode(block, 'REPL', luaOrder) || "''"
      return [`(select(2, string.gsub(${text}, ${pattern}, ${repl})))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_len',
    label: '文本字节长度 %1',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.len(text) 获取字符串字节长度',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`string.len(${text})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_lower',
    label: '转小写 %1',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
    ],
    tooltip: '调用 string.lower(text) 转为小写',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`string.lower(${text})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_match',
    label: '模式匹配 文本 %1 模式 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'PATTERN', check: 'String' },
    ],
    tooltip: '调用 string.match(text, pattern) 提取匹配结果',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const pattern = generator.valueToCode(block, 'PATTERN', luaOrder) || "''"
      return [`string.match(${text}, ${pattern})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_pack',
    label: '打包文本 格式 %1 值1 %2 值2 %3',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
      { type: 'input_value', name: 'VALUE1' },
      { type: 'input_value', name: 'VALUE2' },
    ],
    tooltip: '调用 string.pack(fmt, v1, v2) 按格式打包数据',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      const value1 = generator.valueToCode(block, 'VALUE1', luaOrder) || '0'
      const value2 = generator.valueToCode(block, 'VALUE2', luaOrder) || '0'
      return [`string.pack(${format}, ${value1}, ${value2})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_packsize',
    label: '打包格式长度 %1',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.packsize(fmt) 获取打包格式长度',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      return [`string.packsize(${format})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_rep',
    label: '重复文本 文本 %1 次数 %2',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'COUNT', check: 'Number' },
    ],
    tooltip: '调用 string.rep(text, count) 重复字符串',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const count = generator.valueToCode(block, 'COUNT', luaOrder) || '1'
      return [`string.rep(${text}, ${count})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_reverse',
    label: '反转文本 %1',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
    ],
    tooltip: '调用 string.reverse(text) 反转字符串',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`string.reverse(${text})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_sub',
    label: '截取文本 文本 %1 开始 %2 结束 %3',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
      { type: 'input_value', name: 'START', check: 'Number' },
      { type: 'input_value', name: 'END', check: 'Number' },
    ],
    tooltip: '调用 string.sub(text, start, end) 截取子串',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      const start = generator.valueToCode(block, 'START', luaOrder) || '1'
      const end = generator.valueToCode(block, 'END', luaOrder) || '-1'
      return [`string.sub(${text}, ${start}, ${end})`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_unpack_value1',
    label: '解包值1 格式 %1 数据 %2',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
      { type: 'input_value', name: 'DATA', check: 'String' },
    ],
    tooltip: '调用 string.unpack(format, data) 并返回第 1 个值',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      const data = generator.valueToCode(block, 'DATA', luaOrder) || "''"
      return [`(string.unpack(${format}, ${data}))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_unpack_value2',
    label: '解包值2 格式 %1 数据 %2',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
      { type: 'input_value', name: 'DATA', check: 'String' },
    ],
    tooltip: '调用 string.unpack(format, data) 并返回第 2 个值',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      const data = generator.valueToCode(block, 'DATA', luaOrder) || "''"
      return [`(select(2, string.unpack(${format}, ${data})))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_unpack_nextpos',
    label: '解包下个偏移 格式 %1 数据 %2',
    args: [
      { type: 'input_value', name: 'FORMAT', check: 'String' },
      { type: 'input_value', name: 'DATA', check: 'String' },
    ],
    output: 'Number',
    tooltip: '调用 string.unpack(format, data) 并返回下一个偏移位置',
    generatorCode(block, generator) {
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || "''"
      const data = generator.valueToCode(block, 'DATA', luaOrder) || "''"
      return [`(select(3, string.unpack(${format}, ${data})))`, luaOrder]
    },
  }),
  createStringExpressionBlock({
    type: 'lua_string_upper',
    label: '转大写 %1',
    args: [
      { type: 'input_value', name: 'TEXT', check: 'String' },
    ],
    tooltip: '调用 string.upper(text) 转为大写',
    generatorCode(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`string.upper(${text})`, luaOrder]
    },
  }),
]
