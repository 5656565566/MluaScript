import { luaOrder } from '../constants'

export const deviceBlocks = [
  {
    type: 'maa_click',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '点击 X %1 Y %2',
      args0: [
        { type: 'input_value', name: 'X', check: 'Number' },
        { type: 'input_value', name: 'Y', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '点击设备坐标',
      helpUrl: '',
    },
    generator(block, generator) {
      const x = generator.valueToCode(block, 'X', luaOrder) || '0'
      const y = generator.valueToCode(block, 'Y', luaOrder) || '0'
      return `maa.click(${x}, ${y})\n`
    },
  },
  {
    type: 'maa_swipe',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '滑动 起点X %1 起点Y %2 终点X %3 终点Y %4 时长ms %5',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
        { type: 'input_value', name: 'DURATION', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.swipe() 执行滑动',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      const duration = generator.valueToCode(block, 'DURATION', luaOrder) || '300'
      return `maa.swipe(${x1}, ${y1}, ${x2}, ${y2}, ${duration})\n`
    },
  },
  {
    type: 'maa_input_text',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '输入文本 %1',
      args0: [{ type: 'input_value', name: 'TEXT' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '向当前设备输入文本',
      helpUrl: '',
    },
    generator(block, generator) {
      const text = generator.valueToCode(block, 'TEXT', luaOrder) || "''"
      return `maa.input_text(${text})\n`
    },
  },
  {
    type: 'maa_press_key',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '按键码 %1',
      args0: [{ type: 'input_value', name: 'KEY', check: 'Number' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.press_key() 按下按键',
      helpUrl: '',
    },
    generator(block, generator) {
      const key = generator.valueToCode(block, 'KEY', luaOrder) || '0'
      return `maa.press_key(${key})\n`
    },
  },
  {
    type: 'maa_key_down',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '按下键 %1',
      args0: [{ type: 'input_value', name: 'KEY', check: 'Number' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.key_down() 按下按键(不松开)',
      helpUrl: '',
    },
    generator(block, generator) {
      const key = generator.valueToCode(block, 'KEY', luaOrder) || '0'
      return `maa.key_down(${key})\n`
    },
  },
  {
    type: 'maa_key_up',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '松开键 %1',
      args0: [{ type: 'input_value', name: 'KEY', check: 'Number' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.key_up() 抬起按键',
      helpUrl: '',
    },
    generator(block, generator) {
      const key = generator.valueToCode(block, 'KEY', luaOrder) || '0'
      return `maa.key_up(${key})\n`
    },
  },
  {
    type: 'maa_touch_down',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '手指按下 X %1 Y %2 编号 %3',
      args0: [
        { type: 'input_value', name: 'X', check: 'Number' },
        { type: 'input_value', name: 'Y', check: 'Number' },
        { type: 'input_value', name: 'CONTACT', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.touch_down() 手指按下',
      helpUrl: '',
    },
    generator(block, generator) {
      const x = generator.valueToCode(block, 'X', luaOrder) || '0'
      const y = generator.valueToCode(block, 'Y', luaOrder) || '0'
      const contact = generator.valueToCode(block, 'CONTACT', luaOrder) || '0'
      return `maa.touch_down(${x}, ${y}, ${contact})\n`
    },
  },
  {
    type: 'maa_touch_move',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '手指移动 X %1 Y %2 编号 %3',
      args0: [
        { type: 'input_value', name: 'X', check: 'Number' },
        { type: 'input_value', name: 'Y', check: 'Number' },
        { type: 'input_value', name: 'CONTACT', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.touch_move() 手指移动',
      helpUrl: '',
    },
    generator(block, generator) {
      const x = generator.valueToCode(block, 'X', luaOrder) || '0'
      const y = generator.valueToCode(block, 'Y', luaOrder) || '0'
      const contact = generator.valueToCode(block, 'CONTACT', luaOrder) || '0'
      return `maa.touch_move(${x}, ${y}, ${contact})\n`
    },
  },
  {
    type: 'maa_touch_up',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '手指抬起 编号 %1',
      args0: [
        { type: 'input_value', name: 'CONTACT', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.touch_up() 手指抬起',
      helpUrl: '',
    },
    generator(block, generator) {
      const contact = generator.valueToCode(block, 'CONTACT', luaOrder) || '0'
      return `maa.touch_up(${contact})\n`
    },
  },
  {
    type: 'maa_scroll',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '滚动 dx %1 dy %2',
      args0: [
        { type: 'input_value', name: 'DX', check: 'Number' },
        { type: 'input_value', name: 'DY', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.scroll() 执行滚动',
      helpUrl: '',
    },
    generator(block, generator) {
      const dx = generator.valueToCode(block, 'DX', luaOrder) || '0'
      const dy = generator.valueToCode(block, 'DY', luaOrder) || '0'
      return `maa.scroll(${dx}, ${dy})\n`
    },
  },
  {
    type: 'maa_calc_coordinate',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '计算坐标 真实坐标 %1 真实屏幕宽度/高度 %2',
      args0: [
        { type: 'input_value', name: 'REAL_COORD', check: 'Number' },
        { type: 'input_value', name: 'REAL_SIZE', check: 'Number' },
      ],
      output: 'Number',
      tooltip: '将真实设备上的坐标转换为 MaaFramework 的基准坐标 (如果计算 X 传屏幕宽度, 如果计算 Y 传屏幕高度)',
      helpUrl: '',
    },
    generator(block, generator) {
      const realCoord = generator.valueToCode(block, 'REAL_COORD', luaOrder) || '0'
      const realSize = generator.valueToCode(block, 'REAL_SIZE', luaOrder) || '1920'
      // X/Y 都按 MaaFramework 的短边等比缩放，并对目标尺寸取整。
      return [`((function(res, coord, size) return coord / size * math.floor(size * 720 / math.min(res.width, res.height) + 0.5) end)(maa.get_resolution(), ${realCoord}, ${realSize}))`, luaOrder]
    },
  },
  {
    type: 'maa_start_app',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '启动应用/进程 %1',
      args0: [{ type: 'input_value', name: 'INTENT' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.start_app() 启动应用',
      helpUrl: '',
    },
    generator(block, generator) {
      const intent = generator.valueToCode(block, 'INTENT', luaOrder) || "''"
      return `maa.start_app(${intent})\n`
    },
  },
  {
    type: 'maa_stop_app',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '停止应用/进程 %1',
      args0: [{ type: 'input_value', name: 'INTENT' }],
      previousStatement: null,
      nextStatement: null,
      tooltip: '调用 maa.stop_app() 停止应用',
      helpUrl: '',
    },
    generator(block, generator) {
      const intent = generator.valueToCode(block, 'INTENT', luaOrder) || "''"
      return `maa.stop_app(${intent})\n`
    },
  },
  {
    type: 'maa_shell',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '执行 Shell %1',
      args0: [{ type: 'input_value', name: 'COMMAND' }],
      output: 'String',
      tooltip: '调用 maa.shell() 执行命令',
      helpUrl: '',
    },
    generator(block, generator) {
      const command = generator.valueToCode(block, 'COMMAND', luaOrder) || "''"
      return [`maa.shell(${command})`, luaOrder]
    },
  },
  {
    type: 'maa_screencap',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '获取截图',
      output: null,
      tooltip: '调用 maa.screencap() 获取当前设备截图对象',
      helpUrl: '',
    },
    generator() {
      return ['maa.screencap()', luaOrder]
    },
  },
  {
    type: 'maa_get_uuid',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '获取设备 UUID',
      output: null,
      tooltip: '调用 maa.get_uuid()',
      helpUrl: '',
    },
    generator() {
      return ['maa.get_uuid()', luaOrder]
    },
  },
  {
    type: 'maa_get_resolution',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '获取分辨率文本',
      output: 'String',
      tooltip: '生成一个拼接后的分辨率文本',
      helpUrl: '',
    },
    generator() {
      return ['("resolution:" .. tostring(({maa.get_resolution()})[1]) .. "x" .. tostring(({maa.get_resolution()})[2]))', luaOrder]
    },
  },
  {
    type: 'maa_is_connected',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '设备已连接?',
      output: 'Boolean',
      tooltip: '调用 maa.is_connected()',
      helpUrl: '',
    },
    generator() {
      return ['maa.is_connected()', luaOrder]
    },
  },
  {
    type: 'maa_is_app_alive',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '应用/进程 %1 存活?',
      args0: [{ type: 'input_value', name: 'INTENT' }],
      output: 'Boolean',
      tooltip: '调用 maa.is_app_alive()',
      helpUrl: '',
    },
    generator(block, generator) {
      const intent = generator.valueToCode(block, 'INTENT', luaOrder) || "''"
      return [`maa.is_app_alive(${intent})`, luaOrder]
    },
  },
  {
    type: 'maa_get_connection_label',
    category: '设备信息',
    colour: '#0ea5e9',
    definition: {
      message0: '获取连接标签',
      output: 'String',
      tooltip: '调用 maa.get_connection_label() 获取设备连接标识',
      helpUrl: '',
    },
    generator() {
      return ['maa.get_connection_label()', luaOrder]
    },
  },
  {
    type: 'image_get_width',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '图片 %1 宽度',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: 'Number',
      tooltip: '读取截图/图像对象的宽度',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`(${image}).width`, luaOrder]
    },
  },
  {
    type: 'image_get_height',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '图片 %1 高度',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: 'Number',
      tooltip: '读取截图/图像对象的高度',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`(${image}).height`, luaOrder]
    },
  },
  {
    type: 'image_get_mode',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '图片 %1 模式',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: 'String',
      tooltip: '读取图像模式，例如 RGB / RGBA',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`(${image}).mode`, luaOrder]
    },
  },
  {
    type: 'image_get_channels',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '图片 %1 通道数',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
      ],
      output: 'Number',
      tooltip: '读取图像通道数',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      return [`(${image}).channels`, luaOrder]
    },
  },
  {
    type: 'image_crop',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '裁剪图片 %1 x %2 y %3 宽 %4 高 %5',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
        { type: 'input_value', name: 'X', check: 'Number' },
        { type: 'input_value', name: 'Y', check: 'Number' },
        { type: 'input_value', name: 'W', check: 'Number' },
        { type: 'input_value', name: 'H', check: 'Number' },
      ],
      output: null,
      tooltip: '对截图/图像对象执行裁剪，返回新的图像对象',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      const x = generator.valueToCode(block, 'X', luaOrder) || '0'
      const y = generator.valueToCode(block, 'Y', luaOrder) || '0'
      const w = generator.valueToCode(block, 'W', luaOrder) || '0'
      const h = generator.valueToCode(block, 'H', luaOrder) || '0'
      return [`(${image}):crop(${x}, ${y}, ${w}, ${h})`, luaOrder]
    },
  },
  {
    type: 'image_save',
    category: '图像处理',
    colour: '#0284c7',
    definition: {
      message0: '保存图片 %1 到路径 %2 格式 %3',
      args0: [
        { type: 'input_value', name: 'IMAGE' },
        { type: 'input_value', name: 'PATH' },
        { type: 'input_value', name: 'FORMAT' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '保存截图/图像对象到文件',
      helpUrl: '',
    },
    generator(block, generator) {
      const image = generator.valueToCode(block, 'IMAGE', luaOrder) || 'nil'
      const path = generator.valueToCode(block, 'PATH', luaOrder) || "''"
      const format = generator.valueToCode(block, 'FORMAT', luaOrder) || 'nil'
      return `${image}:save(${path}, ${format})\n`
    },
  },
]
