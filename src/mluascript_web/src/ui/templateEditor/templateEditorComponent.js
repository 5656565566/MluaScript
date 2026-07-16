import {
  NAlert,
  NButton,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NDivider,
  NDynamicInput,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NScrollbar,
  NSelect,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { getWorkspaceProcedureDefinitions } from '../../blockly/utils'
import { actions, state } from '../../store'
import { useTemplateEditor } from './useTemplateEditor'

export default {
  components: {
    NAlert,
    NButton,
    NCheckbox,
    NCollapse,
    NCollapseItem,
    NDivider,
    NDynamicInput,
    NForm,
    NFormItem,
    NInput,
    NInputNumber,
    NModal,
    NScrollbar,
    NSelect,
    NSpace,
    NSwitch,
    NTabPane,
    NTabs,
    NTag,
    NText,
  },
  setup() {
    return useTemplateEditor({
      state,
      message: useMessage(),
      getProcedureDefinitions: getWorkspaceProcedureDefinitions,
      closeEditor: actions.closeTemplateEditor,
      saveEditorMeta: actions.saveTemplateEditorMeta,
    })
  },
}
