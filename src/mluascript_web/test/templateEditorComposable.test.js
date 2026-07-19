import assert from 'node:assert/strict'
import test from 'node:test'
import { nextTick, ref } from 'vue'

import { useTemplateEditor } from '../src/ui/templateEditor/useTemplateEditor.js'

test('模板编辑器公开刷新 Blockly 函数列表的方法', () => {
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(false),
      templateEditorModalData: ref({}),
    },
    message: {
      success() {},
      warning() {},
    },
    getProcedureDefinitions: () => [{
      name: 'run',
      hasReturn: false,
      block: {
        getProcedureDef: () => ['run', ['args'], false],
      },
    }],
    closeEditor() {},
    saveEditorMeta() {},
  })

  assert.equal(typeof editor.refreshProcedureDefinitions, 'function')
  editor.refreshProcedureDefinitions()
  assert.deepEqual(editor.procedureOptions.value, [{
    label: 'run(args)',
    value: 'run',
  }])
})

test('关闭模板编辑器前会刷新最后一次自动保存', async () => {
  const saved = []
  let closed = false
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(true),
      templateEditorModalData: ref({ id: 'autosave_demo' }),
    },
    message: { warning() {} },
    getProcedureDefinitions: () => [],
    closeEditor() {
      closed = true
    },
    saveEditorMeta(payload) {
      saved.push(payload)
    },
  })

  await nextTick()
  editor.localData.value.t = '自动保存标题'
  await nextTick()
  await editor.handleClose()

  assert.equal(saved.at(-1).t, '自动保存标题')
  assert.equal(editor.autosaveStatus.value, 'saved')
  assert.equal(closed, true)
})

test('无效模板不会自动保存，也不能显示为已保存', async () => {
  const saved = []
  const warnings = []
  let closed = false
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(true),
      templateEditorModalData: ref({ id: 'invalid_demo' }),
    },
    message: {
      warning(value) {
        warnings.push(value)
      },
    },
    getProcedureDefinitions: () => [],
    closeEditor() {
      closed = true
    },
    saveEditorMeta(payload) {
      saved.push(payload)
    },
  })

  await nextTick()
  editor.varsList.value.push(editor.createVar())
  await nextTick()

  assert.deepEqual(editor.templateValidationErrors.value, ['参数 1 缺少 Key'])
  assert.equal(editor.autosaveStatus.value, 'invalid')
  assert.equal(editor.autosaveStatusText.value, '配置有错误，尚未保存')

  await editor.handleClose()

  assert.deepEqual(saved, [])
  assert.deepEqual(warnings, ['参数 1 缺少 Key'])
  assert.equal(closed, false)
})

test('编辑器删除资源时同步清理任务流引用', async () => {
  const editor = useTemplateEditor({
    state: {
      templateEditorModalVisible: ref(true),
      templateEditorModalData: ref({
        id: 'delete_demo',
        vars: { stage: { tp: 'str' } },
        tasks: [{ k: 'battle', args: ['stage'] }],
        flows: [{
          k: 'main',
          g: ['stage'],
          steps: [{ k: 'battle_1', task: 'battle', args: { stage: { $bind: 'var', key: 'stage' } } }],
        }],
      }),
    },
    message: { warning() {} },
    getProcedureDefinitions: () => [],
    closeEditor() {},
    saveEditorMeta() {},
  })

  await nextTick()
  const variable = editor.varsList.value[0]
  const task = editor.localData.value.tasks[0]

  assert.equal(editor.getVariableReferenceCount(variable), 4)
  editor.removeVariableDefinition(variable)
  assert.deepEqual(editor.localData.value.tasks[0].args, [])
  assert.deepEqual(editor.localData.value.flows[0].g, [])
  assert.deepEqual(editor.localData.value.flows[0].steps[0].args, {})

  assert.equal(editor.getTaskReferenceCount(task), 1)
  editor.removeTaskDefinition(task)
  assert.deepEqual(editor.localData.value.flows[0].steps, [])
})
