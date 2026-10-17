import { luaOrder } from '../constants.js'
import { buildQuickInputShadows } from '../quickInput.js'
import { getWorkspaceVariablesOfType } from '../workspaceVariables.js'

function provideNameValidator(generator) {
  return generator.provideFunction_('mlua_reflection_name', [
    `local function ${generator.FUNCTION_NAME_PLACEHOLDER_}(name)`,
    '  if type(name) ~= "string" then error("反射名称必须是字符串", 2) end',
    '  return name',
    'end',
  ])
}

function getBlocklyNames(workspace, generator, kind) {
  const procedures = workspace.getAllBlocks(false).filter(block =>
    block.type === 'procedures_defnoreturn' || block.type === 'procedures_defreturn')
  if (kind === 'function') {
    return new Map(procedures.map(block => {
      const name = block.getFieldValue('NAME')
      return [name, generator.getProcedureName(name)]
    }))
  }

  const argumentIds = new Set(procedures.flatMap(block =>
    (block.getVarModels() || []).map(model => model.getId())))
  return new Map(getWorkspaceVariablesOfType(workspace)
    .filter(model => !argumentIds.has(model.getId()))
    .map(model => [model.name, generator.getVariableName(model.getId())]))
}

function generateEnvironmentLookup(block, generator, kind) {
  const name = generator.valueToCode(block, 'NAME', luaOrder) || "''"
  const validateName = provideNameValidator(generator)
  if (block.getFieldValue('NAME_MODE') === 'RAW') {
    return `_G[${validateName}(${name})]`
  }

  const helperKey = `mlua_reflection_${kind}`
  if (!generator.definitions_[helperKey]) {
    const names = getBlocklyNames(block.workspace, generator, kind)
    const entries = [...names].map(([original, generated]) =>
      `    [${generator.quote_(original)}] = ${generator.quote_(generated)},`)
    // 映射属于当前文件；通过 upvalue 随闭包复制到子任务，模块之间不会互相覆盖。
    generator.provideFunction_(helperKey, [
      `local ${generator.FUNCTION_NAME_PLACEHOLDER_} = (function()`,
      '  local names = {',
      ...entries,
      '  }',
      '  return function(name)',
      `    local key = names[${validateName}(name)]`,
      '    if key == nil then return nil end',
      '    return _G[key]',
      '  end',
      'end)()',
    ])
  }
  return `${generator.functionNames_[helperKey]}(${name})`
}

function generateCall(block, generator) {
  const target = generator.valueToCode(block, 'FUNCTION', luaOrder) || 'nil'
  const args = generator.valueToCode(block, 'ARGS', luaOrder) || '{}'
  const call = generator.provideFunction_('mlua_reflection_call', [
    `local function ${generator.FUNCTION_NAME_PLACEHOLDER_}(target, args)`,
    '  if type(args) ~= "table" then error("反射调用的参数必须是列表", 2) end',
    '  local count = args.n',
    '  if count == nil then count = #args end',
    '  if type(count) ~= "number" or count < 0 or count % 1 ~= 0 then',
    '    error("反射调用的参数数量必须是非负整数", 2)',
    '  end',
    // 直接调用也支持宿主暴露的 callable userdata，并保留参数及返回值中的 nil。
    '  return target(table.unpack(args, 1, count))',
    'end',
  ])
  return `${call}(${target}, ${args})`
}

function nameInputs() {
  return [
    { type: 'input_value', name: 'NAME', check: 'String' },
    {
      type: 'field_dropdown',
      name: 'NAME_MODE',
      options: [['拼图名称', 'BLOCKLY'], ['Lua 原始键', 'RAW']],
    },
  ]
}

function callInputs() {
  return [
    { type: 'input_value', name: 'FUNCTION' },
    { type: 'input_value', name: 'ARGS' },
  ]
}

function callToolboxInputs() {
  return {
    FUNCTION: {
      shadow: {
        type: 'reflection_get_function',
        inputs: buildQuickInputShadows({ args0: nameInputs() }),
      },
    },
  }
}

export const luaReflectionBlocks = [
  {
    type: 'reflection_get_global',
    category: '反射',
    colour: '#7c3aed',
    definition: {
      message0: '获取环境变量 名称 %1 按 %2',
      args0: nameInputs(),
      output: null,
      tooltip: '按字符串读取 _G 中的变量。拼图名称使用实际生成的名称映射；Lua 原始键直接查找。不存在时返回 nil，不能读取局部变量或参数。',
      helpUrl: '',
    },
    generator(block, generator) {
      return [generateEnvironmentLookup(block, generator, 'variable'), luaOrder]
    },
  },
  {
    type: 'reflection_get_shared',
    category: '反射',
    colour: '#7c3aed',
    definition: {
      message0: '获取共享状态 名称 %1',
      args0: [{ type: 'input_value', name: 'NAME', check: 'String' }],
      output: null,
      tooltip: '按字符串读取共享状态。中文名称保持原文，不做标识符转换；不存在时返回 nil。',
      helpUrl: '',
    },
    generator(block, generator) {
      const name = generator.valueToCode(block, 'NAME', luaOrder) || "''"
      return [`shared.get_key(${provideNameValidator(generator)}(${name}))`, luaOrder]
    },
  },
  {
    type: 'reflection_get_function',
    category: '反射',
    colour: '#7c3aed',
    definition: {
      message0: '获取函数引用 名称 %1 按 %2',
      args0: nameInputs(),
      output: 'LuaFunction',
      tooltip: '按字符串获取全局函数引用，可连接到反射调用块。拼图名称支持中文及重名转换；不存在时返回 nil，可调用性在调用时检查。',
      helpUrl: '',
    },
    generator(block, generator) {
      return [generateEnvironmentLookup(block, generator, 'function'), luaOrder]
    },
  },
  {
    type: 'reflection_call',
    category: '反射',
    colour: '#7c3aed',
    toolboxInputs: callToolboxInputs(),
    definition: {
      message0: '调用函数 %1 参数列表 %2',
      args0: callInputs(),
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用函数并忽略返回值。默认按名称获取引用，也可替换为保存函数的变量。参数列表留空表示无参数；使用打包为表可保留 nil 参数。',
      helpUrl: '',
    },
    generator(block, generator) {
      return `${generateCall(block, generator)}\n`
    },
  },
  {
    type: 'reflection_call_return',
    category: '反射',
    colour: '#7c3aed',
    toolboxInputs: callToolboxInputs(),
    definition: {
      message0: '调用函数并获取结果 %1 参数列表 %2',
      args0: callInputs(),
      output: null,
      tooltip: '调用函数并返回结果，遵循 Lua 多返回值规则。默认按名称获取引用，也可替换为保存函数的变量。参数列表留空表示无参数；使用打包为表可保留 nil 参数。',
      helpUrl: '',
    },
    generator(block, generator) {
      return [generateCall(block, generator), luaOrder]
    },
  },
]
