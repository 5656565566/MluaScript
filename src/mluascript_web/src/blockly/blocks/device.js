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
    type: 'maa_human_swipe',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '模拟人手滑动 起点X %1 起点Y %2 终点X %3 终点Y %4 时长ms %5 轨迹点数 %6 抖动 %7 贝塞尔 %8 起止偏移 %9 末端停顿 %10 速度模板 %11 方向模板 %12',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
        { type: 'input_value', name: 'DURATION', check: 'Number' },
        { type: 'input_value', name: 'STEPS', check: 'Number' },
        { type: 'input_value', name: 'JITTER', check: 'Number' },
        { type: 'input_value', name: 'USE_BEZIER', check: 'Boolean' },
        { type: 'input_value', name: 'USE_ENDPOINT_OFFSET', check: 'Boolean' },
        { type: 'input_value', name: 'USE_END_PAUSE', check: 'Boolean' },
        { type: 'input_value', name: 'USE_SPEED_PROFILE', check: 'Boolean' },
        { type: 'input_value', name: 'USE_DIRECTION_PROFILE', check: 'Boolean' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '更自然的滑动。推荐：短滑 250~450ms，翻页 500~900ms；轨迹点数 0=自动，短距离 10~16，长距离 18~30；抖动 0.3~0.8 更稳，0.8~1.8 更自然。贝塞尔通常开启；小目标拖动建议关闭起止偏移；末端停顿适合翻页；速度模板一般开启；方向模板适合长距离上下/左右滑动。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      const duration = generator.valueToCode(block, 'DURATION', luaOrder) || '600'
      const steps = generator.valueToCode(block, 'STEPS', luaOrder) || '0'
      const jitter = generator.valueToCode(block, 'JITTER', luaOrder) || '1.2'
      const useBezier = generator.valueToCode(block, 'USE_BEZIER', luaOrder) || 'true'
      const useEndpointOffset = generator.valueToCode(block, 'USE_ENDPOINT_OFFSET', luaOrder) || 'true'
      const useEndPause = generator.valueToCode(block, 'USE_END_PAUSE', luaOrder) || 'true'
      const useSpeedProfile = generator.valueToCode(block, 'USE_SPEED_PROFILE', luaOrder) || 'true'
      const useDirectionProfile = generator.valueToCode(block, 'USE_DIRECTION_PROFILE', luaOrder) || 'true'
      return `maa.human_swipe(${x1}, ${y1}, ${x2}, ${y2}, ${duration}, ${steps}, ${jitter}, 0, ${useBezier}, ${useEndpointOffset}, ${useEndPause}, ${useSpeedProfile}, ${useDirectionProfile})\n`
    },
  },
  {
    type: 'maa_human_swipe_preset_steady',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '模拟人手短滑(稳) 起点X %1 起点Y %2 终点X %3 终点Y %4',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '稳定优先。适合小目标拖动、短距离精确滑动。默认关闭起止偏移，低抖动。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      return `maa.human_swipe(${x1}, ${y1}, ${x2}, ${y2}, 360, 12, 0.45, 0, true, false, false, true, false)\n`
    },
  },
  {
    type: 'maa_human_swipe_preset_natural',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '模拟人手翻页(自然) 起点X %1 起点Y %2 终点X %3 终点Y %4',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '自然优先。适合长距离翻页、上下滑动浏览。默认开启贝塞尔、起止偏移、末端停顿、速度模板和方向模板。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      return `maa.human_swipe(${x1}, ${y1}, ${x2}, ${y2}, 720, 22, 1.15, 0, true, true, true, true, true)\n`
    },
  },
  {
    type: 'maa_human_swipe_preset_drag_precise',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '模拟人手精准拖动 起点X %1 起点Y %2 终点X %3 终点Y %4',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '精度优先。适合滑块、拖动物体、小范围位移。低抖动，高点数，关闭起止偏移与末端停顿。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      return `maa.human_swipe(${x1}, ${y1}, ${x2}, ${y2}, 520, 20, 0.35, 0, true, false, false, true, false)\n`
    },
  },
  {
    type: 'maa_human_swipe_preset_scroll_vertical',
    category: '设备交互',
    colour: '#059669',
    definition: {
      message0: '模拟人手纵向长滑 起点X %1 起点Y %2 终点X %3 终点Y %4',
      args0: [
        { type: 'input_value', name: 'X1', check: 'Number' },
        { type: 'input_value', name: 'Y1', check: 'Number' },
        { type: 'input_value', name: 'X2', check: 'Number' },
        { type: 'input_value', name: 'Y2', check: 'Number' },
      ],
      previousStatement: null,
      nextStatement: null,
      tooltip: '适合列表滚动、页面浏览、上下长滑。开启方向模板和末端停顿，轨迹更像真实翻页。',
      helpUrl: '',
    },
    generator(block, generator) {
      const x1 = generator.valueToCode(block, 'X1', luaOrder) || '0'
      const y1 = generator.valueToCode(block, 'Y1', luaOrder) || '0'
      const x2 = generator.valueToCode(block, 'X2', luaOrder) || '0'
      const y2 = generator.valueToCode(block, 'Y2', luaOrder) || '0'
      return `maa.human_swipe(${x1}, ${y1}, ${x2}, ${y2}, 820, 26, 1.0, 0, true, true, true, true, true)\n`
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
      return [`(${realCoord} / ${realSize} * 1280)`, luaOrder]
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
