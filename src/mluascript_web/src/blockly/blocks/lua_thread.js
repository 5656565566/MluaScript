import * as Blockly from 'blockly'
import { luaOrder } from '../constants'
import { attachBlockSemanticWarning, getBlockSemanticDiagnostic } from '../blockSemanticDiagnostics'

function getSharedVarName(block) {
  return String(block.getFieldValue('VAR_NAME') || '').trim()
}

function getSharedVarKey(block) {
  return JSON.stringify(getSharedVarName(block))
}

function getTaskHandle(block, generator) {
  return generator.valueToCode(block, 'HANDLE', luaOrder) || 'nil'
}

export const luaThreadBlocks = [
  {
    type: 'maa_run_pipeline',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '执行流水线 %1',
      args0: [{ type: 'input_value', name: 'ENTRY' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.run_pipeline()。运行 maa pipeline。',
      helpUrl: '',
    },
    generator(block, generator) {
      const entry = generator.valueToCode(block, 'ENTRY', luaOrder) || "''"
      return `maa.run_pipeline(${entry})\n`
    },
  },
  {
    type: 'thread_spawn_function',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '作为任务运行 %1',
      args0: [{ type: 'input_statement', name: 'FUNC_CALL' }],
      output: 'ThreadTask',
      tooltip: '将普通的【调用函数】块拖入此处，使其在后台作为任务运行并提取参数。',
      helpUrl: '',
    },
    init(block) {
      attachBlockSemanticWarning(block)
    },
    generator(block, generator) {
      const diagnostic = getBlockSemanticDiagnostic(block)
      if (diagnostic) throw new Error(diagnostic)
      const targetBlock = block.getInputTargetBlock('FUNC_CALL')

      let rawFuncName = ''
      if (targetBlock.type === 'procedure_call_picker') {
        rawFuncName = targetBlock.getFieldValue('PROC_NAME') || ''
      } else {
        rawFuncName = targetBlock.getFieldValue('NAME') || ''
      }
      
      const funcName = generator.nameDB_ ? generator.nameDB_.getName(rawFuncName, Blockly.PROCEDURE_CATEGORY_NAME || 'PROCEDURE') : rawFuncName
      
      const args = []
      let i = 0
      while (targetBlock.getInput('ARG' + i)) {
        const argCode = generator.valueToCode(targetBlock, 'ARG' + i, luaOrder) || 'nil'
        args.push(argCode)
        i++
      }

      const argsString = args.length > 0 ? `, nil, ${args.join(', ')}` : ''
      return [`thread.spawn(${JSON.stringify(funcName)}${argsString})`, luaOrder]
    },
  },
  {
    type: 'thread_join',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '等待线程 %1 超时秒 %2',
      args0: [
        { type: 'input_value', name: 'HANDLE', check: 'ThreadTask' },
        { type: 'input_value', name: 'TIMEOUT', check: 'Number' },
      ],
      output: 'Boolean',
      tooltip: '调用线程任务句柄的 join(timeout)。',
      helpUrl: '',
    },
    generator(block, generator) {
      const handle = getTaskHandle(block, generator)
      const timeout = generator.valueToCode(block, 'TIMEOUT', luaOrder) || '0'
      return [`(${handle}):join(${timeout})`, luaOrder]
    },
  },
  {
    type: 'thread_cancel',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '取消线程 %1',
      args0: [{ type: 'input_value', name: 'HANDLE', check: 'ThreadTask' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用线程任务句柄的 cancel()。',
      helpUrl: '',
    },
    generator(block, generator) {
      const handle = getTaskHandle(block, generator)
      return `(${handle}):cancel()\n`
    },
  },
  {
    type: 'thread_is_running',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '线程允许继续运行?',
      output: 'Boolean',
      tooltip: '子线程内可用，宿主取消时 is_cancelled() 会返回 true。',
      helpUrl: '',
    },
    generator() {
      return [`(not (is_cancelled and is_cancelled()))`, luaOrder]
    },
  },
  {
    type: 'thread_alive',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '线程运行中? %1',
      args0: [{ type: 'input_value', name: 'HANDLE', check: 'ThreadTask' }],
      output: 'Boolean',
      tooltip: '调用线程任务句柄的 is_alive()。',
      helpUrl: '',
    },
    generator(block, generator) {
      const handle = getTaskHandle(block, generator)
      return [`(${handle}):is_alive()`, luaOrder]
    },
  },
  {
    type: 'shared_var_get',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '读取全局状态 %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      output: null,
      tooltip: '从 runtime 全局共享表读取指定键。',
      helpUrl: '',
    },
    generator(block) {
      return [`shared.get_key(${getSharedVarKey(block)})`, luaOrder]
    },
  },
  {
    type: 'shared_var_set',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '设置全局状态 %1 为 %2',
      args0: [
        { type: 'field_shared_variable', name: 'VAR_NAME', text: '' },
        { type: 'input_value', name: 'VALUE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '写入 runtime 全局共享表指定键。',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `shared.set_key(${getSharedVarKey(block)}, ${value})\n`
    },
  },
  {
    type: 'shared_var_truthy',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '全局状态为真? %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      output: 'Boolean',
      tooltip: '判断指定全局共享键是否严格等于 true。',
      helpUrl: '',
    },
    generator(block) {
      return [`(shared.get_key(${getSharedVarKey(block)}) == true)`, luaOrder]
    },
  },
  {
    type: 'shared_var_get_key',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '取键值 变量 %1 键名 %2',
      args0: [
        { type: 'field_shared_variable', name: 'VAR_NAME', text: '' },
        { type: 'input_value', name: 'KEY' },
      ],
      output: null,
      tooltip: '把全局状态值当作 table，再读取其中一个键。',
      helpUrl: '',
    },
    generator(block, generator) {
      const parentKey = getSharedVarKey(block)
      const key = generator.valueToCode(block, 'KEY', luaOrder) || "''"
      return [`((shared.get_key(${parentKey}) or {})[${key}])`, luaOrder]
    },
  },
  {
    type: 'shared_var_set_key',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '设键值 变量 %1 键名 %2 值 %3',
      args0: [
        { type: 'field_shared_variable', name: 'VAR_NAME', text: '' },
        { type: 'input_value', name: 'KEY' },
        { type: 'input_value', name: 'VALUE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '把全局状态值当作 table，设置其中一个键后写回。',
      helpUrl: '',
    },
    generator(block, generator) {
      const parentKey = getSharedVarKey(block)
      const key = generator.valueToCode(block, 'KEY', luaOrder) || "''"
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `do\n  local __mlua_shared_value = shared.get_key(${parentKey}) or {}\n  __mlua_shared_value[${key}] = ${value}\n  shared.set_key(${parentKey}, __mlua_shared_value)\nend\n`
    },
  },
  {
    type: 'shared_var_append',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '追加元素 变量 %1 值 %2',
      args0: [
        { type: 'field_shared_variable', name: 'VAR_NAME', text: '' },
        { type: 'input_value', name: 'VALUE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '把全局状态值当作列表追加元素后写回。',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || 'nil'
      return `do\n  local __mlua_shared_value = shared.get_key(${getSharedVarKey(block)}) or {}\n  table.insert(__mlua_shared_value, ${value})\n  shared.set_key(${getSharedVarKey(block)}, __mlua_shared_value)\nend\n`
    },
  },
  {
    type: 'shared_var_size',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '容器大小 变量 %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      output: 'Number',
      tooltip: '返回全局状态 table/list 的长度。',
      helpUrl: '',
    },
    generator(block) {
      return [`#(shared.get_key(${getSharedVarKey(block)}) or {})`, luaOrder]
    },
  },
  {
    type: 'shared_var_is_nil',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '是空值? 变量 %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      output: 'Boolean',
      tooltip: '判断指定全局共享键是否为 nil。',
      helpUrl: '',
    },
    generator(block) {
      return [`(shared.get_key(${getSharedVarKey(block)}) == nil)`, luaOrder]
    },
  },
  {
    type: 'shared_var_clear',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '清空数据 变量 %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '把指定全局共享键设置为 nil。',
      helpUrl: '',
    },
    generator(block) {
      return `shared.set_key(${getSharedVarKey(block)}, nil)\n`
    },
  },
  {
    type: 'shared_var_to_json',
    category: '全局状态',
    colour: '#10b981',
    definition: {
      message0: '转为JSON 变量 %1',
      args0: [{ type: 'field_shared_variable', name: 'VAR_NAME', text: '' }],
      output: 'String',
      tooltip: '把指定全局共享值编码为 JSON。',
      helpUrl: '',
    },
    generator(block) {
      return [`json_encode(shared.get_key(${getSharedVarKey(block)}))`, luaOrder]
    },
  },
]
