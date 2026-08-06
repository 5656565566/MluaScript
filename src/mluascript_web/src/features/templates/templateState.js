import { ref } from 'vue'

export function createTemplateState() {
  return {
    selectedTemplateScript: ref(null),
    selectedTemplateMeta: ref(null),
    selectedTemplateConfigPath: ref(''),
    selectedTemplateSavedConfig: ref(null),
    templateScriptType: ref(''),
    templateTaskFormData: ref({}),
    templateWorkflowFormData: ref({}),
    templateReadme: ref(null),
    templateRunnerTab: ref(''),
    selectedTaskKey: ref(''),
    selectedWorkflowKey: ref(''),
    selectedWorkflowStepKey: ref(''),
  }
}
