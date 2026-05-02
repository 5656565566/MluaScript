import * as Blockly from 'blockly'
import { luaOrder, PICKER_ICON_TYPE } from '../constants'
import { getLuaScriptPickerItems, getWorkspaceFunctionPickerItems } from '../utils'
import { MaaPickerIcon } from '../fields'
import { luaMathBlocks } from './lua_math'
import { luaStringBlocks } from './lua_string'

export const luaCoreBlocks = [
  {
    type: 'lua_notify',
    category: '调试 / 输出',
    colour: '#4f46e5',
    definition: {
      message0: '通知 %1',
      args0: [{ type: 'input_value', name: 'MESSAGE' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 notify 输出提示信息',
      helpUrl: '',
    },
    generator(block, generator) {
      const message = generator.valueToCode(block, 'MESSAGE', luaOrder) || "''"
      return `notify(${message})\n`
    },
  },
  {
    type: 'lua_print',
    category: '调试 / 输出',
    colour: '#4f46e5',
    definition: {
      message0: '输出 %1',
      args0: [{ type: 'input_value', name: 'TEXT' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 print 输出文本',
      helpUrl: '',
    },
    generator(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return `print(${text})\n`
    },
  },
  {
    type: 'lua_log',
    category: '调试 / 输出',
    colour: '#4f46e5',
    definition: {
      message0: '日志 等级 %1 内容 %2',
      args0: [
        {
          type: 'field_dropdown',
          name: 'LEVEL',
          options: [
            ['TRACE', 'trace'],
            ['DEBUG', 'debug'],
            ['INFO', 'info'],
            ['WARN', 'warn'],
            ['ERROR', 'error'],
          ],
        },
        { type: 'input_value', name: 'MESSAGE' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 log_* 输出不同等级的日志',
      helpUrl: '',
    },
    generator(block, generator) {
      const level = block.getFieldValue('LEVEL') || 'info'
      const message = generator.valueToCode(block, 'MESSAGE', luaOrder) || "''"
      return `log_${level}(${message})\n`
    },
  },
  {
    type: 'lua_sleep',
    category: '运行控制',
    colour: '#4f46e5',
    definition: {
      message0: '等待 %1 秒',
      args0: [{ type: 'input_value', name: 'SECONDS', check: 'Number' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 sleep 暂停执行；宿主会在等待期间持续检查停止信号。',
      helpUrl: '',
    },
    generator(block, generator) {
      const seconds = generator.valueToCode(block, 'SECONDS', luaOrder) || '1'
      return `sleep(${seconds})\n`
    },
  },
  {
    type: 'lua_check_stop',
    category: '运行控制',
    colour: '#4f46e5',
    definition: {
      message0: '检查停止信号',
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 check_stop()；如果宿主请求停止，当前脚本会立即中断。',
      helpUrl: '',
    },
    generator() {
      return 'check_stop()\n'
    },
  },
  {
    type: 'lua_stop_script',
    category: '运行控制',
    colour: '#4f46e5',
    definition: {
      message0: '停止脚本 %1',
      args0: [{ type: 'input_value', name: 'MESSAGE' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 stop 结束脚本执行。当前宿主实现未接收参数，提示信息仅作界面保留。',
      helpUrl: '',
    },
    generator() {
      return 'stop()\n'
    },
  },
  {
    type: 'lua_require_module_stmt',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '导入模块 %1 %2',
      args0: [
        { type: 'field_label', name: 'MODULE_LABEL', text: '未选择' },
        { type: 'field_label', name: 'CONFIG_TEXT', text: '配置' }
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '执行 require("模块名") 导入模块。适合只触发模块初始化、副作用加载。',
      helpUrl: '',
    },
    init(block) {
      block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'MODULE_VALUE').setVisible(false)
      if (!block.getIcon(PICKER_ICON_TYPE)) {
        block.addIcon(new MaaPickerIcon(block, () => ({
          title: '选择模块',
          items: getLuaScriptPickerItems(true),
          currentValue: block.getFieldValue('MODULE_VALUE'),
          onSelect: (selectedValue) => {
            block.setFieldValue(selectedValue, 'MODULE_LABEL')
            block.setFieldValue(selectedValue, 'MODULE_VALUE')
          }
        })))
      }
      // 从隐藏值字段恢复显示标签（XML 加载后 field_label 不会被序列化）
      const savedValue = block.getFieldValue('MODULE_VALUE')
      if (savedValue) {
        block.setFieldValue(savedValue, 'MODULE_LABEL')
      }
    },
    generator(block) {
      const moduleName = JSON.stringify(block.getFieldValue('MODULE_VALUE') || '')
      if (moduleName === '""') return '-- 未选择模块\n'
      return `require(${moduleName})\n`
    },
  },
  {
    type: 'lua_require_module_expr',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '导入模块值 %1 %2',
      args0: [
        { type: 'field_label', name: 'MODULE_LABEL', text: '未选择' },
        { type: 'field_label', name: 'CONFIG_TEXT', text: '配置' }
      ],
      output: null,
      tooltip: '生成 require("模块名") 表达式，可接变量赋值或函数调用。',
      helpUrl: '',
    },
    init(block) {
      block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'MODULE_VALUE').setVisible(false)
      if (!block.getIcon(PICKER_ICON_TYPE)) {
        block.addIcon(new MaaPickerIcon(block, () => ({
          title: '选择模块',
          items: getLuaScriptPickerItems(true),
          currentValue: block.getFieldValue('MODULE_VALUE'),
          onSelect: (selectedValue) => {
            block.setFieldValue(selectedValue, 'MODULE_LABEL')
            block.setFieldValue(selectedValue, 'MODULE_VALUE')
          }
        })))
      }
      // 从隐藏值字段恢复显示标签（XML 加载后 field_label 不会被序列化）
      const savedValue = block.getFieldValue('MODULE_VALUE')
      if (savedValue) {
        block.setFieldValue(savedValue, 'MODULE_LABEL')
      }
    },
    generator(block) {
      const moduleName = JSON.stringify(block.getFieldValue('MODULE_VALUE') || '')
      if (moduleName === '""') return ['nil -- 未选择模块', luaOrder]
      return [`require(${moduleName})`, luaOrder]
    },
  },
  {
    type: 'lua_dofile_stmt',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '执行 Lua 文件 %1 %2',
      args0: [
        { type: 'field_label', name: 'FILE_LABEL', text: '未选择' },
        { type: 'field_label', name: 'CONFIG_TEXT', text: '配置' }
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '执行 dofile("相对路径.lua")。路径相对当前主脚本所在目录。',
      helpUrl: '',
    },
    init(block) {
      block.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'FILE_VALUE').setVisible(false)
      if (!block.getIcon(PICKER_ICON_TYPE)) {
        block.addIcon(new MaaPickerIcon(block, () => ({
          title: '选择 Lua 文件',
          items: getLuaScriptPickerItems(false),
          currentValue: block.getFieldValue('FILE_VALUE'),
          onSelect: (selectedValue) => {
            block.setFieldValue(selectedValue, 'FILE_LABEL')
            block.setFieldValue(selectedValue, 'FILE_VALUE')
          }
        })))
      }
      // 从隐藏值字段恢复显示标签（XML 加载后 field_label 不会被序列化）
      const savedValue = block.getFieldValue('FILE_VALUE')
      if (savedValue) {
        block.setFieldValue(savedValue, 'FILE_LABEL')
      }
    },
    generator(block) {
      const filePath = JSON.stringify(block.getFieldValue('FILE_VALUE') || '')
      if (filePath === '""') return '-- 未选择文件\n'
      return `dofile(${filePath})\n`
    },
  },
  {
    type: 'lua_module_export_function',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '模块导出 %1 %2',
      args0: [
        { type: 'field_label', name: 'FUNC_LABEL', text: '未选择函数' },
        { type: 'field_label', name: 'CONFIG_TEXT', text: '配置' }
      ],
      tooltip: '模块导出根块。用于声明文件末尾 return 导出表，只允许工作区存在一个。',
      helpUrl: '',
    },
    init(block) {
      block.setDeletable(true)
      block.setMovable(true)
      block.setEditable(true)
      block.appendDummyInput().appendField(new Blockly.FieldTextInput('[]'), 'FUNC_VALUES').setVisible(false)
      if (!block.getIcon(PICKER_ICON_TYPE)) {
        block.addIcon(new MaaPickerIcon(block, () => ({
          title: '选择要导出的函数',
          items: getWorkspaceFunctionPickerItems(),
          currentValue: (() => {
            try {
              return JSON.parse(block.getFieldValue('FUNC_VALUES') || '[]')
            } catch {
              return []
            }
          })(),
          multiple: true,
          onSelect: (selectedValues) => {
            const values = Array.isArray(selectedValues) ? selectedValues : []
            block.setFieldValue(JSON.stringify(values), 'FUNC_VALUES')
            if (!values.length) {
              block.setFieldValue('未选择函数', 'FUNC_LABEL')
            } else if (values.length <= 2) {
              block.setFieldValue(values.join('，'), 'FUNC_LABEL')
            } else {
              block.setFieldValue(`${values[0]} 等 ${values.length} 个`, 'FUNC_LABEL')
            }
          }
        })))
      }
      // 从隐藏值字段恢复显示标签（XML 加载后 field_label 不会被序列化）
      try {
        const savedFuncValues = JSON.parse(block.getFieldValue('FUNC_VALUES') || '[]')
        if (Array.isArray(savedFuncValues) && savedFuncValues.length > 0) {
          if (savedFuncValues.length <= 2) {
            block.setFieldValue(savedFuncValues.join('，'), 'FUNC_LABEL')
          } else {
            block.setFieldValue(`${savedFuncValues[0]} 等 ${savedFuncValues.length} 个`, 'FUNC_LABEL')
          }
        }
      } catch (e) {}
      block.setOnChange((event) => {
        const workspace = block.workspace
        if (!workspace) return
        const exportBlocks = workspace.getTopBlocks(false).filter((item) => item?.type === 'lua_module_export_function')
        if (exportBlocks.length > 1) {
          block.setWarningText('模块导出根块只能存在一个')
        } else {
          block.setWarningText(null)
        }

        // 自动同步函数改名
        if (event && event.type === Blockly.Events.BLOCK_CHANGE && event.element === 'field' && event.name === 'NAME') {
          const changedBlock = workspace.getBlockById(event.blockId)
          if (changedBlock && (changedBlock.type === 'procedures_defnoreturn' || changedBlock.type === 'procedures_defreturn')) {
            const oldName = event.oldValue
            const newName = event.newValue
            if (oldName && newName && oldName !== newName) {
              try {
                const currentValues = JSON.parse(block.getFieldValue('FUNC_VALUES') || '[]')
                const index = currentValues.indexOf(oldName)
                if (index !== -1) {
                  currentValues[index] = newName
                  block.setFieldValue(JSON.stringify(currentValues), 'FUNC_VALUES')
                  if (!currentValues.length) {
                    block.setFieldValue('未选择函数', 'FUNC_LABEL')
                  } else if (currentValues.length <= 2) {
                    block.setFieldValue(currentValues.join('，'), 'FUNC_LABEL')
                  } else {
                    block.setFieldValue(`${currentValues[0]} 等 ${currentValues.length} 个`, 'FUNC_LABEL')
                  }
                }
              } catch (e) {
              }
            }
          }
        }
      })
    },
    generator() {
      return ''
    },
  },
  {
    type: 'lua_get_time',
    category: '时间',
    colour: '#9333ea',
    definition: {
      message0: '获取当前时间(秒)',
      output: 'Number',
      tooltip: '调用 os.time() 获取当前时间戳(秒)',
      helpUrl: '',
    },
    generator() {
      return ['os.time()', luaOrder]
    },
  },
  {
    type: 'lua_format_time',
    category: '时间',
    colour: '#9333ea',
    definition: {
      message0: '格式化耗时 %1 (秒)',
      args0: [{ type: 'input_value', name: 'SECONDS', check: 'Number' }],
      output: 'String',
      tooltip: '将秒数转换为 xx h xx m xx s 格式',
      helpUrl: '',
    },
    generator(block, generator) {
      const seconds = generator.valueToCode(block, 'SECONDS', luaOrder) || '0'
      return [`format_time(${seconds})`, luaOrder]
    },
  },
  {
    type: 'lua_length_not_zero',
    category: null,
    definition: {
      style: 'logic_blocks',
      message0: '长度不为 0 %1',
      args0: [{ type: 'input_value', name: 'VALUE' }],
      output: 'Boolean',
      tooltip: '判断列表、字符串或结果集长度是否不为 0',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '{}'
      return [`(#(${value} or {}) > 0)`, luaOrder]
    },
  },
  {
    type: 'lua_to_number',
    category: null,
    definition: {
      style: 'math_blocks',
      message0: '转为数字 %1',
      args0: [{ type: 'input_value', name: 'VALUE' }],
      output: 'Number',
      tooltip: '将字符串或其他类型转换为数字',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || '0'
      return [`(tonumber(${value}) or 0)`, luaOrder]
    },
  },
  ...luaMathBlocks,
  {
    type: 'lua_rawequal',
    category: null,
    definition: {
      style: 'logic_blocks',
      message0: '原始相等 %1 和 %2',
      args0: [
        { type: 'input_value', name: 'A' },
        { type: 'input_value', name: 'B' },
      ],
      output: 'Boolean',
      tooltip: '调用 rawequal(a, b) 进行原始值比较，不触发元方法',
      helpUrl: '',
    },
    generator(block, generator) {
      const a = generator.valueToCode(block, 'A', luaOrder) || 'nil'
      const b = generator.valueToCode(block, 'B', luaOrder) || 'nil'
      return [`rawequal(${a}, ${b})`, luaOrder]
    },
  },
  {
    type: 'lua_package_config',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '包配置 package.config',
      output: 'String',
      tooltip: '读取 package.config 常量',
      helpUrl: '',
    },
    generator() {
      return ['package.config', luaOrder]
    },
  },
  {
    type: 'lua_package_loaded',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '已加载模块表 package.loaded',
      output: null,
      tooltip: '读取 package.loaded 表',
      helpUrl: '',
    },
    generator() {
      return ['package.loaded', luaOrder]
    },
  },
  {
    type: 'lua_package_path',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '模块搜索路径 package.path',
      output: 'String',
      tooltip: '读取 package.path 字符串',
      helpUrl: '',
    },
    generator() {
      return ['package.path', luaOrder]
    },
  },
  {
    type: 'lua_package_set_path',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '设置模块搜索路径 %1',
      args0: [{ type: 'input_value', name: 'VALUE', check: 'String' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '设置 package.path',
      helpUrl: '',
    },
    generator(block, generator) {
      const value = generator.valueToCode(block, 'VALUE', luaOrder) || "''"
      return `package.path = ${value}\n`
    },
  },
  {
    type: 'lua_package_preload',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '预加载模块表 package.preload',
      output: null,
      tooltip: '读取 package.preload 表',
      helpUrl: '',
    },
    generator() {
      return ['package.preload', luaOrder]
    },
  },
  {
    type: 'lua_package_searchers',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '模块搜索器列表 package.searchers',
      output: null,
      tooltip: '读取 package.searchers 表',
      helpUrl: '',
    },
    generator() {
      return ['package.searchers', luaOrder]
    },
  },
  {
    type: 'lua_package_loadlib',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '加载 C 库 路径 %1 入口函数 %2',
      args0: [
        { type: 'input_value', name: 'LIB', check: 'String' },
        { type: 'input_value', name: 'FUNC', check: 'String' },
      ],
      output: null,
      tooltip: '调用 package.loadlib(lib, funcname) 动态加载 C 库',
      helpUrl: '',
    },
    generator(block, generator) {
      const lib = generator.valueToCode(block, 'LIB', luaOrder) || "''"
      const func = generator.valueToCode(block, 'FUNC', luaOrder) || "''"
      return [`package.loadlib(${lib}, ${func})`, luaOrder]
    },
  },
  {
    type: 'lua_package_searchpath',
    category: '模块 / 文件',
    colour: '#7c3aed',
    definition: {
      message0: '搜索模块路径 模块名 %1 路径串 %2',
      args0: [
        { type: 'input_value', name: 'NAME', check: 'String' },
        { type: 'input_value', name: 'PATH', check: 'String' },
      ],
      output: 'String',
      tooltip: '调用 package.searchpath(name, path) 返回匹配到的文件路径或 nil',
      helpUrl: '',
    },
    generator(block, generator) {
      const name = generator.valueToCode(block, 'NAME', luaOrder) || "''"
      const path = generator.valueToCode(block, 'PATH', luaOrder) || 'package.path'
      return [`package.searchpath(${name}, ${path})`, luaOrder]
    },
  },
  ...luaStringBlocks,
]
