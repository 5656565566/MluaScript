import { ChevronDown } from '@vicons/ionicons5'
import { ref } from 'vue'
import {
  NButton,
  NIcon,
  NModal,
  NSpace,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { getWorkspaceProcedureDefinitions } from '../../blockly/utils'
import { actions, state } from '../../store'
import TemplateAuxiliaryDialogs from './TemplateAuxiliaryDialogs.vue'
import TemplateFlowWorkbench from './TemplateFlowWorkbench.vue'
import TemplateResourceDialogs from './TemplateResourceDialogs.vue'
import PaginatedSearchSelect from './PaginatedSearchSelect.vue'
import { useTemplateEditor } from './useTemplateEditor'

export default {
  components: {
    ChevronDown,
    NButton,
    NIcon,
    NModal,
    NSpace,
    NTag,
    NText,
    PaginatedSearchSelect,
    TemplateAuxiliaryDialogs,
    TemplateFlowWorkbench,
    TemplateResourceDialogs,
  },
  setup() {
    const summaryExpanded = ref(false)
    const editor = useTemplateEditor({
      state,
      message: useMessage(),
      getProcedureDefinitions: getWorkspaceProcedureDefinitions,
      closeEditor: actions.closeTemplateEditor,
      saveEditorMeta: actions.saveTemplateEditorMeta,
    })
    return { ...editor, flowEditor: editor, summaryExpanded }
  },
}
