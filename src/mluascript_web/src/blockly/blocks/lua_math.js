import { luaOrder } from '../constants'

function createMathFunctionBlock({ type, label, method, args, output = 'Number', tooltip }) {
  return {
    type,
    category: null,
    definition: {
      style: 'math_blocks',
      message0: label,
      args0: args,
      output,
      tooltip,
      helpUrl: '',
    },
    generator(block, generator) {
      const argCodes = args.map((arg, index) => {
        if (arg.type !== 'input_value') return null
        const fallback = arg.check === 'Number' ? '0' : "''"
        return generator.valueToCode(block, arg.name, luaOrder) || fallback
      }).filter((item) => item !== null)
      return [`math.${method}(${argCodes.join(', ')})`, luaOrder]
    },
  }
}

function createMathConstantBlock({ type, label, constant, tooltip }) {
  return {
    type,
    category: null,
    definition: {
      style: 'math_blocks',
      message0: label,
      output: 'Number',
      tooltip,
      helpUrl: '',
    },
    generator() {
      return [`math.${constant}`, luaOrder]
    },
  }
}

export const luaMathBlocks = [
  createMathFunctionBlock({
    type: 'lua_math_abs',
    label: '绝对值 %1',
    method: 'abs',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.abs(x) 返回绝对值',
  }),
  createMathFunctionBlock({
    type: 'lua_math_acos',
    label: '反余弦 %1',
    method: 'acos',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.acos(x) 返回反余弦（弧度）',
  }),
  createMathFunctionBlock({
    type: 'lua_math_asin',
    label: '反正弦 %1',
    method: 'asin',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.asin(x) 返回反正弦（弧度）',
  }),
  createMathFunctionBlock({
    type: 'lua_math_atan',
    label: '反正切 %1',
    method: 'atan',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.atan(x) 返回反正切（弧度）',
  }),
  createMathFunctionBlock({
    type: 'lua_math_ceil',
    label: '向上取整 %1',
    method: 'ceil',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.ceil(x) 向上取整',
  }),
  createMathFunctionBlock({
    type: 'lua_math_cos',
    label: '余弦 %1',
    method: 'cos',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.cos(x) 返回余弦值',
  }),
  createMathFunctionBlock({
    type: 'lua_math_deg',
    label: '弧度转角度 %1',
    method: 'deg',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.deg(x) 将弧度转换为角度',
  }),
  createMathFunctionBlock({
    type: 'lua_math_exp',
    label: '指数运算 %1',
    method: 'exp',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.exp(x) 计算 e^x',
  }),
  createMathFunctionBlock({
    type: 'lua_math_floor',
    label: '向下取整 %1',
    method: 'floor',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.floor(x) 向下取整',
  }),
  createMathFunctionBlock({
    type: 'lua_math_fmod',
    label: '取模 %1 ÷ %2',
    method: 'fmod',
    args: [
      { type: 'input_value', name: 'DIVIDEND', check: 'Number' },
      { type: 'input_value', name: 'DIVISOR', check: 'Number' },
    ],
    tooltip: '调用 math.fmod(x, y) 计算取模结果',
  }),
  createMathFunctionBlock({
    type: 'lua_math_log',
    label: '对数 真数 %1 底数 %2',
    method: 'log',
    args: [
      { type: 'input_value', name: 'VALUE', check: 'Number' },
      { type: 'input_value', name: 'BASE', check: 'Number' },
    ],
    tooltip: '调用 math.log(x, base) 计算对数',
  }),
  createMathFunctionBlock({
    type: 'lua_math_max',
    label: '最大值 %1 和 %2',
    method: 'max',
    args: [
      { type: 'input_value', name: 'A', check: 'Number' },
      { type: 'input_value', name: 'B', check: 'Number' },
    ],
    tooltip: '调用 math.max(a, b) 取较大值',
  }),
  createMathFunctionBlock({
    type: 'lua_math_min',
    label: '最小值 %1 和 %2',
    method: 'min',
    args: [
      { type: 'input_value', name: 'A', check: 'Number' },
      { type: 'input_value', name: 'B', check: 'Number' },
    ],
    tooltip: '调用 math.min(a, b) 取较小值',
  }),
  {
    type: 'lua_math_modf_integer',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '分离整数部分 %1',
      args0: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
      output: 'Number',
      tooltip: '调用 math.modf(x) 并返回整数部分',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '0'
      return [`(math.modf(${value}))`, luaOrder]
    },
  },
  {
    type: 'lua_math_modf_fraction',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '分离小数部分 %1',
      args0: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
      output: 'Number',
      tooltip: '调用 math.modf(x) 并返回小数部分',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '0'
      return [`(select(2, math.modf(${value})))`, luaOrder]
    },
  },
  createMathFunctionBlock({
    type: 'lua_math_rad',
    label: '角度转弧度 %1',
    method: 'rad',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.rad(x) 将角度转换为弧度',
  }),
  {
    type: 'lua_math_random',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '随机整数 从 %1 到 %2',
      args0: [
        { type: 'input_value', name: 'MIN', check: 'Number' },
        { type: 'input_value', name: 'MAX', check: 'Number' },
      ],
      output: 'Number',
      tooltip: '调用 math.random(min, max) 生成区间随机整数',
      helpUrl: '',
    },
    generator(block, generator) {
      const min = generator.valueToCode(block, 'MIN', luaOrder) || '1'
      const max = generator.valueToCode(block, 'MAX', luaOrder) || '100'
      return [`math.random(${min}, ${max})`, luaOrder]
    },
  },
  {
    type: 'lua_random_range',
    category: null,
    definition: {
      message0: '随机数 从 %1 到 %2',
      args0: [
        { type: 'input_value', name: 'MIN', check: 'Number' },
        { type: 'input_value', name: 'MAX', check: 'Number' },
      ],
      style: 'math_blocks',
      output: 'Number',
      tooltip: '调用 random_range(min, max) 生成随机数。',
      helpUrl: '',
    },
    generator(block, generator) {
      const min = generator.valueToCode(block, 'MIN', luaOrder) || '0'
      const max = generator.valueToCode(block, 'MAX', luaOrder) || '1'
      return [`random_range(${min}, ${max})`, luaOrder]
    },
  },
  {
    type: 'lua_math_randomseed',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '设置随机种子 %1',
      args0: [{ type: 'input_value', name: 'SEED', check: 'Number' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 math.randomseed(seed) 设置随机数种子',
      helpUrl: '',
    },
    generator(block, generator) {
      const seed = generator.valueToCode(block, 'SEED', luaOrder) || 'os.time()'
      return `math.randomseed(${seed})\n`
    },
  },
  createMathFunctionBlock({
    type: 'lua_math_sin',
    label: '正弦 %1',
    method: 'sin',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.sin(x) 返回正弦值',
  }),
  createMathFunctionBlock({
    type: 'lua_math_sqrt',
    label: '平方根 %1',
    method: 'sqrt',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.sqrt(x) 计算平方根',
  }),
  createMathFunctionBlock({
    type: 'lua_math_tan',
    label: '正切 %1',
    method: 'tan',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.tan(x) 返回正切值',
  }),
  createMathFunctionBlock({
    type: 'lua_math_tointeger',
    label: '转为整数 %1',
    method: 'tointeger',
    args: [{ type: 'input_value', name: 'VALUE', check: 'Number' }],
    tooltip: '调用 math.tointeger(x) 转换为整数，失败返回 nil',
  }),
  {
    type: 'lua_math_type',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '数值类型 %1',
      args0: [{ type: 'input_value', name: 'VALUE' }],
      output: 'String',
      tooltip: '调用 math.type(x) 返回 integer、float 或 nil',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '0'
      return [`math.type(${value})`, luaOrder]
    },
  },
  {
    type: 'lua_math_ult',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '无符号比较 %1 < %2',
      args0: [
        { type: 'input_value', name: 'A', check: 'Number' },
        { type: 'input_value', name: 'B', check: 'Number' },
      ],
      output: 'Boolean',
      tooltip: '调用 math.ult(a, b) 按无符号整数比较大小',
      helpUrl: '',
    },
    generator(block, generator) {
      const a = generator.valueToCode(block, 'A', luaOrder) || '0'
      const b = generator.valueToCode(block, 'B', luaOrder) || '0'
      return [`math.ult(${a}, ${b})`, luaOrder]
    },
  },
  createMathConstantBlock({
    type: 'lua_math_pi',
    label: '圆周率 π',
    constant: 'pi',
    tooltip: 'math.pi 常量',
  }),
  createMathConstantBlock({
    type: 'lua_math_huge',
    label: '无穷大',
    constant: 'huge',
    tooltip: 'math.huge 常量',
  }),
  createMathConstantBlock({
    type: 'lua_math_maxinteger',
    label: '最大整数',
    constant: 'maxinteger',
    tooltip: 'math.maxinteger 常量',
  }),
  createMathConstantBlock({
    type: 'lua_math_mininteger',
    label: '最小整数',
    constant: 'mininteger',
    tooltip: 'math.mininteger 常量',
  }),
]
