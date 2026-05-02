import { luaOrder } from '../constants'

export const luaCoroutineBlocks = [
  {
    type: 'coroutine_create',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '创建协程任务 %1',
      args0: [
        {
          type: 'input_statement',
          name: 'DO',
        },
      ],
      output: null,
      tooltip: '创建一个协程并返回协程对象 (coroutine.create)。内嵌要执行的代码块。',
      helpUrl: '',
    },
    generator(block, generator) {
      const branch = generator.statementToCode(block, 'DO') || ''
      return [`coroutine.create(function()\n${branch}end)`, luaOrder]
    },
  },
  {
    type: 'coroutine_resume',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '运行/恢复协程 %1',
      args0: [{ type: 'input_value', name: 'CO' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '恢复协程的运行状态 (coroutine.resume)',
      helpUrl: '',
    },
    generator(block, generator) {
      const co = generator.valueToCode(block, 'CO', luaOrder) || 'nil'
      return `coroutine.resume(${co})\n`
    },
  },
  {
    type: 'coroutine_resume_with_value',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '恢复协程 %1 传入参数 %2',
      args0: [
        { type: 'input_value', name: 'CO' },
        { type: 'input_value', name: 'VAL' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '恢复协程，并将参数传递给上次 yield 的返回值',
      helpUrl: '',
    },
    generator(block, generator) {
      const co = generator.valueToCode(block, 'CO', luaOrder) || 'nil'
      const val = generator.valueToCode(block, 'VAL', luaOrder) || 'nil'
      return `coroutine.resume(${co}, ${val})\n`
    },
  },
  {
    type: 'coroutine_yield',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '挂起当前协程',
      previousStatement: null,
      nextStatement: null,
      tooltip: '暂停当前正在执行的协程，将控制权交还给 resume (coroutine.yield)',
      helpUrl: '',
    },
    generator() {
      return `coroutine.yield()\n`
    },
  },
  {
    type: 'coroutine_yield_value',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '挂起并返回值 %1',
      args0: [{ type: 'input_value', name: 'VAL' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '暂停当前协程，并向外层 resume 返回一个值',
      helpUrl: '',
    },
    generator(block, generator) {
      const val = generator.valueToCode(block, 'VAL', luaOrder) || 'nil'
      return `coroutine.yield(${val})\n`
    },
  },
  {
    type: 'coroutine_status',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '协程状态 %1',
      args0: [{ type: 'input_value', name: 'CO' }],
      output: 'String',
      tooltip: '获取协程的运行状态 (返回 running, suspended, normal 或 dead)',
      helpUrl: '',
    },
    generator(block, generator) {
      const co = generator.valueToCode(block, 'CO', luaOrder) || 'nil'
      return [`coroutine.status(${co})`, luaOrder]
    },
  },
  {
    type: 'coroutine_isyieldable',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '当前协程可挂起?',
      output: 'Boolean',
      tooltip: '检查当前运行的协程是否允许被 yield 挂起 (Lua 5.3+)',
      helpUrl: '',
    },
    generator() {
      return [`coroutine.isyieldable()`, luaOrder]
    },
  },
  {
    type: 'coroutine_close',
    category: '协程',
    colour: '#d97706',
    definition: {
      message0: '关闭协程 %1',
      args0: [{ type: 'input_value', name: 'CO' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '关闭协程，将其置为 dead 状态并释放 pending 的待关闭变量 (Lua 5.4 专属)',
      helpUrl: '',
    },
    generator(block, generator) {
      const co = generator.valueToCode(block, 'CO', luaOrder) || 'nil'
      return `coroutine.close(${co})\n`
    },
  },
]
