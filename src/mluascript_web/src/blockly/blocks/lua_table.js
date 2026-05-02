import { luaOrder } from '../constants'

function createTableExpressionBlock({ type, label, args, output = null, tooltip, generatorCode }) {
  return {
    type,
    category: '数据表',
    colour: '#0369a1',
    definition: {
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

function createTableStatementBlock({ type, label, args, tooltip, generatorCode }) {
  return {
    type,
    category: '数据表',
    colour: '#0369a1',
    definition: {
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

export const luaTableBlocks = [
  {
    type: 'lua_table_get_field',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '读取表字段 表 %1 键名 %2',
      args0: [
        { type: 'input_value', name: 'TABLE' },
        { type: 'input_value', name: 'FIELD' },
      ],
      output: null,
      tooltip: '读取任意表字段的值 (table[key])',
      helpUrl: '',
    },
    generator(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const field = generator.valueToCode(block, 'FIELD', luaOrder) || "''"
      return [`${table}[${field}]`, luaOrder]
    },
  },
  {
    type: 'lua_table_set_field',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '设置表字段 表 %1 键名 %2 值 %3',
      args0: [
        { type: 'input_value', name: 'TABLE' },
        { type: 'input_value', name: 'FIELD' },
        { type: 'input_value', name: 'VALUE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '设置表字段的值 (table[key] = value)',
      helpUrl: '',
    },
    generator(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const field = generator.valueToCode(block, 'FIELD', luaOrder) || "''"
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `${table}[${field}] = ${value}\n`
    },
  },
  {
    type: 'lua_table_get_index',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '读取列表项 列表 %1 索引 %2',
      args0: [
        { type: 'input_value', name: 'TABLE' },
        { type: 'input_value', name: 'INDEX', check: 'Number' },
      ],
      output: null,
      tooltip: '读取列表指定索引的值 (table[index]) Lua 索引从 1 开始',
      helpUrl: '',
    },
    generator(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const index = generator.valueToCode(block, 'INDEX', luaOrder) || '1'
      return [`${table}[${index}]`, luaOrder]
    },
  },
  {
    type: 'lua_table_set_index',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '设置列表项 列表 %1 索引 %2 值 %3',
      args0: [
        { type: 'input_value', name: 'TABLE' },
        { type: 'input_value', name: 'INDEX', check: 'Number' },
        { type: 'input_value', name: 'VALUE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '设置列表指定索引的值 (table[index] = value)，Lua 索引从 1 开始',
      helpUrl: '',
    },
    generator(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const index = generator.valueToCode(block, 'INDEX', luaOrder) || '1'
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `${table}[${index}] = ${value}\n`
    },
  },
  {
    type: 'lua_table_length',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '获取列表长度 列表 %1',
      args0: [
        { type: 'input_value', name: 'TABLE' },
      ],
      output: 'Number',
      tooltip: '获取列表的长度 (#table)',
      helpUrl: '',
    },
    generator(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      return [`#(${table})`, luaOrder]
    },
  },
  {
    type: 'lua_table_create',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '创建空表 {}',
      output: null,
      tooltip: '创建一个空的 Lua 表 {}',
      helpUrl: '',
    },
    generator() {
      return ['{}', luaOrder]
    },
  },
  createTableStatementBlock({
    type: 'lua_table_insert',
    label: '追加到列表 列表 %1 值 %2',
    args: [
      { type: 'input_value', name: 'TABLE' },
      { type: 'input_value', name: 'VALUE' },
    ],
    tooltip: '向列表末尾追加一个值 (table.insert)',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `table.insert(${table}, ${value})\n`
    },
  }),
  createTableStatementBlock({
    type: 'lua_table_insert_at',
    label: '插入到列表 列表 %1 位置 %2 值 %3',
    args: [
      { type: 'input_value', name: 'TABLE' },
      { type: 'input_value', name: 'POSITION', check: 'Number' },
      { type: 'input_value', name: 'VALUE' },
    ],
    tooltip: '调用 table.insert(list, pos, value) 在指定位置插入元素',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const position = generator.valueToCode(block, 'POSITION', luaOrder) || '1'
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `table.insert(${table}, ${position}, ${value})\n`
    },
  }),
  createTableExpressionBlock({
    type: 'lua_table_concat',
    label: '连接列表元素 列表 %1 分隔符 %2',
    args: [
      { type: 'input_value', name: 'TABLE' },
      { type: 'input_value', name: 'SEP', check: 'String' },
    ],
    output: 'String',
    tooltip: '调用 table.concat(list, sep) 连接数组元素',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const sep = generator.valueToCode(block, 'SEP', luaOrder) || "''"
      return [`table.concat(${table}, ${sep})`, luaOrder]
    },
  }),
  createTableExpressionBlock({
    type: 'lua_table_move',
    label: '移动表元素 源表 %1 开始 %2 结束 %3 目标起点 %4 目标表 %5',
    args: [
      { type: 'input_value', name: 'SOURCE' },
      { type: 'input_value', name: 'FROM', check: 'Number' },
      { type: 'input_value', name: 'TO', check: 'Number' },
      { type: 'input_value', name: 'TARGET_START', check: 'Number' },
      { type: 'input_value', name: 'TARGET' },
    ],
    output: null,
    tooltip: '调用 table.move(source, from, to, targetStart, target) 移动元素块',
    generatorCode(block, generator) {
      const source = generator.valueToCode(block, 'SOURCE', luaOrder) || '{}'
      const from = generator.valueToCode(block, 'FROM', luaOrder) || '1'
      const to = generator.valueToCode(block, 'TO', luaOrder) || '1'
      const targetStart = generator.valueToCode(block, 'TARGET_START', luaOrder) || '1'
      const target = generator.valueToCode(block, 'TARGET', luaOrder) || '{}'
      return [`table.move(${source}, ${from}, ${to}, ${targetStart}, ${target})`, luaOrder]
    },
  }),
  createTableExpressionBlock({
    type: 'lua_table_pack',
    label: '打包为表 值1 %1 值2 %2 值3 %3',
    args: [
      { type: 'input_value', name: 'VALUE1' },
      { type: 'input_value', name: 'VALUE2' },
      { type: 'input_value', name: 'VALUE3' },
    ],
    output: null,
    tooltip: '调用 table.pack(v1, v2, v3) 打包参数为表，保留 nil 位置',
    generatorCode(block, generator) {
      const value1 = generator.valueToCode(block, 'VALUE1', luaOrder) || 'nil'
      const value2 = generator.valueToCode(block, 'VALUE2', luaOrder) || 'nil'
      const value3 = generator.valueToCode(block, 'VALUE3', luaOrder) || 'nil'
      return [`table.pack(${value1}, ${value2}, ${value3})`, luaOrder]
    },
  }),
  createTableExpressionBlock({
    type: 'lua_table_remove',
    label: '删除列表项 列表 %1 位置 %2',
    args: [
      { type: 'input_value', name: 'TABLE' },
      { type: 'input_value', name: 'POSITION', check: 'Number' },
    ],
    output: null,
    tooltip: '调用 table.remove(list, pos) 删除元素并返回被删值',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      const position = generator.valueToCode(block, 'POSITION', luaOrder) || '1'
      return [`table.remove(${table}, ${position})`, luaOrder]
    },
  }),
  createTableStatementBlock({
    type: 'lua_table_sort',
    label: '排序列表 %1',
    args: [
      { type: 'input_value', name: 'TABLE' },
    ],
    tooltip: '调用 table.sort(list) 对列表元素升序排序',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      return `table.sort(${table})\n`
    },
  }),
  createTableExpressionBlock({
    type: 'lua_table_unpack',
    label: '展开表 列表 %1',
    args: [
      { type: 'input_value', name: 'TABLE' },
    ],
    output: null,
    tooltip: '调用 table.unpack(list) 展开表为多返回值',
    generatorCode(block, generator) {
      const table = generator.valueToCode(block, 'TABLE', luaOrder) || '{}'
      return [`table.unpack(${table})`, luaOrder]
    },
  }),
  {
    type: 'lua_json_encode',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: '表转 JSON 字符串 %1',
      args0: [
        { type: 'input_value', name: 'VALUE' },
      ],
      output: 'String',
      tooltip: '将表转换为 JSON 字符串',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '{}'
      return [`json_encode(${value})`, luaOrder]
    },
  },
  {
    type: 'lua_json_decode',
    category: '数据表',
    colour: '#0369a1',
    definition: {
      message0: 'JSON 字符串转表 %1',
      args0: [
        { type: 'input_value', name: 'TEXT', check: 'String' },
      ],
      output: null,
      tooltip: '将 JSON 字符串解析为表',
      helpUrl: '',
    },
    generator(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return [`json_decode(${text})`, luaOrder]
    },
  },
]
