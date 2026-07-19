export const BLOCKLY_ZH_CN_OVERRIDES = Object.freeze({
  CONTROLS_IF_MSG_IF: '如果',
  CONTROLS_REPEAT_TITLE: '重复 %1 次',
  CONTROLS_REPEAT_INPUT_DO: '循环',
  LOGIC_BOOLEAN_TRUE: '真',
  LOGIC_BOOLEAN_FALSE: '假',
  TEXT_JOIN_TITLE_CREATEWITH: '拼接文本',
  VARIABLES_DEFAULT_NAME: '项目',
  PROCEDURES_DEFNORETURN_TITLE: '定义',
  PROCEDURES_DEFNORETURN_PROCEDURE: '函数',
  PROCEDURES_DEFRETURN_TITLE: '定义',
  PROCEDURES_DEFRETURN_PROCEDURE: '函数',
  TEXT_APPEND_TO: '追加到',
  CONTROLS_WHILEUNTIL_OPERATOR_WHILE: '当',
  CONTROLS_WHILEUNTIL_OPERATOR_UNTIL: '直到',
  // Blockly 13.1.1 的 zh-hans 暂时混入了繁体复制提示，在这里统一为 zh-CN。
  KEYBOARD_NAV_COPIED_HINT: '已复制。按下 %1 粘贴。',
  KEYBOARD_NAV_CUT_HINT: '已剪切。按下 %1 粘贴。',
})

export function applyBlocklyZhCnLocale(Blockly, locale) {
  Blockly.setLocale(locale)
  Object.assign(Blockly.Msg, BLOCKLY_ZH_CN_OVERRIDES)
}
