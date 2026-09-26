import * as Blockly from 'blockly'
import { luaOrder, PICKER_ICON_TYPE } from '../constants'
import { attachBlockSemanticWarning } from '../blockSemanticDiagnostics'
import { MaaPickerIcon } from '../fields'
import {
  createThreadTaskPickerConfig,
  generateThreadTask,
  generateThreadTaskId,
  installThreadTaskSerialization,
  restoreThreadTaskSelection,
} from '../threadTaskSelection.js'
import { state } from '../../store.js'
import { pickerActions } from '../../store/pickerState.js'

function getSharedVarName(block) {
  return String(block.getFieldValue('VAR_NAME') || '').trim()
}

function getSharedVarKey(block) {
  return JSON.stringify(getSharedVarName(block))
}

function getTaskHandle(block, generator) {
  return generator.valueToCode(block, 'HANDLE', luaOrder) || 'nil'
}

function initializeThreadTaskPicker(block) {
  block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'TARGET_KIND').setVisible(false)
  block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'MODULE_VALUE').setVisible(false)
  block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'FUNCTION_VALUE').setVisible(false)
  block.appendDummyInput().appendField(new Blockly.FieldTextInput('[]'), 'PARAM_VALUES').setVisible(false)
  block.appendDummyInput().appendField(new Blockly.FieldTextInput('function'), 'CALL_STYLE').setVisible(false)
  installThreadTaskSerialization(block)
  if (!block.getIcon(PICKER_ICON_TYPE)) {
    block.addIcon(new MaaPickerIcon(block, () =>
      createThreadTaskPickerConfig(block, state.projectSelectedPath?.value, pickerActions.update)))
  }
  restoreThreadTaskSelection(block)
  attachBlockSemanticWarning(block, () => restoreThreadTaskSelection(block))
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
    type: 'thread_spawn_selected_function',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '作为任务运行 %1',
      args0: [{ type: 'field_label', name: 'TARGET_LABEL', text: '未选择函数' }],
      output: 'ThreadTask',
      tooltip: '选择当前文件或项目模块中的一个函数，填写参数后作为后台任务运行。',
      helpUrl: '',
    },
    init(block) { initializeThreadTaskPicker(block) },
    generator: generateThreadTask,
  },
  {
    type: 'thread_task_id',
    category: '任务',
    colour: '#10b981',
    definition: {
      message0: '获取任务 ID %1',
      args0: [{ type: 'input_value', name: 'HANDLE', check: 'ThreadTask' }],
      output: 'String',
      tooltip: '读取后台任务句柄的 ID。',
      helpUrl: '',
    },
    generator: generateThreadTaskId,
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
