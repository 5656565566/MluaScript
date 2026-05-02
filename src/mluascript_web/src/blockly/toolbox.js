import { dynamicBlockSpecs } from './blocks'

export const baseCategories = [
  {
    kind: 'category',
    name: '逻辑',
    categorystyle: 'logic_category',
    contents: [
      { kind: 'block', type: 'controls_if' },
      { kind: 'block', type: 'logic_compare' },
      { kind: 'block', type: 'logic_boolean' },
      { kind: 'block', type: 'logic_negate' },
      { kind: 'block', type: 'lua_length_not_zero' },
      { kind: 'block', type: 'lua_rawequal' },
    ],
  },
  {
    kind: 'category',
    name: '循环',
    categorystyle: 'loop_category',
    contents: [
      { kind: 'block', type: 'controls_repeat_ext' },
      { kind: 'block', type: 'controls_whileUntil' },
      { kind: 'block', type: 'controls_for' },
    ],
  },
  {
    kind: 'category',
    name: '数学',
    categorystyle: 'math_category',
    contents: [
      { kind: 'block', type: 'math_number' },
      { kind: 'block', type: 'math_arithmetic' },
      { kind: 'block', type: 'math_round' },
      { kind: 'block', type: 'lua_to_number' },
      { kind: 'block', type: 'lua_math_abs' },
      { kind: 'block', type: 'lua_math_acos' },
      { kind: 'block', type: 'lua_math_asin' },
      { kind: 'block', type: 'lua_math_atan' },
      { kind: 'block', type: 'lua_math_ceil' },
      { kind: 'block', type: 'lua_math_cos' },
      { kind: 'block', type: 'lua_math_deg' },
      { kind: 'block', type: 'lua_math_exp' },
      { kind: 'block', type: 'lua_math_floor' },
      { kind: 'block', type: 'lua_math_fmod' },
      { kind: 'block', type: 'lua_math_log' },
      { kind: 'block', type: 'lua_math_max' },
      { kind: 'block', type: 'lua_math_min' },
      { kind: 'block', type: 'lua_math_modf_integer' },
      { kind: 'block', type: 'lua_math_modf_fraction' },
      { kind: 'block', type: 'lua_math_rad' },
      { kind: 'block', type: 'lua_math_random' },
      { kind: 'block', type: 'lua_random_range' },
      { kind: 'block', type: 'lua_math_randomseed' },
      { kind: 'block', type: 'lua_math_sin' },
      { kind: 'block', type: 'lua_math_sqrt' },
      { kind: 'block', type: 'lua_math_tan' },
      { kind: 'block', type: 'lua_math_tointeger' },
      { kind: 'block', type: 'lua_math_type' },
      { kind: 'block', type: 'lua_math_ult' },
      { kind: 'block', type: 'lua_math_pi' },
      { kind: 'block', type: 'lua_math_huge' },
      { kind: 'block', type: 'lua_math_maxinteger' },
      { kind: 'block', type: 'lua_math_mininteger' },
    ],
  },
  {
    kind: 'category',
    name: '文本',
    categorystyle: 'text_category',
    contents: [
      { kind: 'block', type: 'text' },
      { kind: 'block', type: 'text_join' },
      { kind: 'block', type: 'text_length' },
      { kind: 'block', type: 'lua_string_byte' },
      { kind: 'block', type: 'lua_string_char' },
      { kind: 'block', type: 'lua_string_dump' },
      { kind: 'block', type: 'lua_string_find_start' },
      { kind: 'block', type: 'lua_string_find_end' },
      { kind: 'block', type: 'lua_string_format' },
      { kind: 'block', type: 'lua_string_gmatch' },
      { kind: 'block', type: 'lua_string_gsub_text' },
      { kind: 'block', type: 'lua_string_gsub_count' },
      { kind: 'block', type: 'lua_string_len' },
      { kind: 'block', type: 'lua_string_lower' },
      { kind: 'block', type: 'lua_string_match' },
      { kind: 'block', type: 'lua_string_pack' },
      { kind: 'block', type: 'lua_string_packsize' },
      { kind: 'block', type: 'lua_string_rep' },
      { kind: 'block', type: 'lua_string_reverse' },
      { kind: 'block', type: 'lua_string_sub' },
      { kind: 'block', type: 'lua_string_unpack_value1' },
      { kind: 'block', type: 'lua_string_unpack_value2' },
      { kind: 'block', type: 'lua_string_unpack_nextpos' },
      { kind: 'block', type: 'lua_string_upper' },
    ],
  },
  {
    kind: 'category',
    name: '函数',
    contents: [
      { kind: 'block', type: 'procedures_defnoreturn' },
      { kind: 'block', type: 'procedures_defreturn' },
      { kind: 'block', type: 'procedures_ifreturn' },
      { kind: 'block', type: 'procedure_call_picker' },
      { kind: 'block', type: 'procedure_arg_get' },
      { kind: 'block', type: 'template_arg_get' },
      { kind: 'block', type: 'procedure_arg_set' },
    ],
  },
  {
    kind: 'category',
    name: '变量',
    custom: 'VARIABLE',
    contents: [
      { kind: 'block', type: 'local_var_declare' },
      { kind: 'block', type: 'variables_set' },
      { kind: 'block', type: 'math_change' },
      { kind: 'block', type: 'variables_get' },
    ],
  },
]

export function buildDynamicCategories() {
  const map = new Map()
  for (const spec of dynamicBlockSpecs) {
    if (!spec.category) continue
    if (!map.has(spec.category)) {
      map.set(spec.category, {
        kind: 'category',
        name: spec.category,
        colour: spec.colour,
        contents: [],
      })
    }
    map.get(spec.category).contents.push({ kind: 'block', type: spec.type })
  }
  return [...map.values()]
}

export function buildToolbox() {
  return {
    kind: 'categoryToolbox',
    contents: [...baseCategories, ...buildDynamicCategories()],
  }
}
