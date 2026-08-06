import { ref } from 'vue'

export function createProjectState() {
  return {
    projects: ref([]),
    currentProject: ref(null),
    currentManifest: ref(null),
    projectTree: ref([]),
    projectModules: ref([]),
    projectOpenFiles: ref([]),
    projectSelectedPath: ref(''),
    projectFile: ref(null),
    projectFileContent: ref(''),
    projectFileDirty: ref(false),
    projectGeneratedLua: ref(''),
    projectGeneratedLuaStale: ref(false),
    projectBlocklyDiagnostics: ref([]),
    projectLuaPreviewVisible: ref(false),
    projectDiagnostics: ref([]),
    projectLoading: ref(false),
    projectFileOperationLoading: ref(false),
    projectBuildLoading: ref(false),
    projectBuildResult: ref(null),
    projectDebugLoading: ref(false),
    projectDebugTaskByKey: ref({}),
  }
}
