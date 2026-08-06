const PICKER_HANDLER_NAMES = [
  'onSelect',
  'onConfirm',
  'onCreate',
  'onManage',
  'onOpenFieldPicker',
]

export function mergePickerHandlers(currentHandlers = {}, patch = {}) {
  return Object.fromEntries(PICKER_HANDLER_NAMES.map((name) => [
    name,
    Object.prototype.hasOwnProperty.call(patch, name) ? patch[name] : currentHandlers[name],
  ]))
}
