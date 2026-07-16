import { ref } from 'vue'

export function createRuntimeState() {
  return {
    tasks: ref([]),
    taskDetailById: ref({}),
    taskLogsById: ref({}),
    taskOutputById: ref({}),
    blocklyFiles: ref([]),
    luaFiles: ref([]),
    availableScripts: ref([]),
    logs: ref([]),
    selectedPipeline: ref(''),
    selectedTaskId: ref(''),
    taskTraceLevelFilter: ref('all'),
    runtimeState: ref('idle'),
    sharedVariableRegistryVersion: ref(0),
    userCreatedSharedVariables: ref([]),
  }
}
