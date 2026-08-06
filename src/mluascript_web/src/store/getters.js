import { computed } from 'vue'

export function createGetters(state) {
  return {
    imageUrl: computed(() => state.screenshotBase64.value ? `data:image/png;base64,${state.screenshotBase64.value}` : ''),
    pipelineTasks: computed(() => state.tasks.value.filter(item => item.kind === 'pipeline')),
    luaScriptFiles: computed(() => state.luaFiles.value.map(item => ({
      ...item,
      name: item.name || item.filename || item.path,
    }))),
    filteredTaskManagerTasks: computed(() => {
      const keyword = state.taskManagerQuery.value.trim().toLowerCase()
      if (!keyword) return state.tasks.value
      return state.tasks.value.filter((item) => {
        const title = item.title || item.name || item.metadata?.entry || item.metadata?.script_path || ''
        return [title, item.task_id, item.kind, item.status, item.target, item.name]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(keyword)
      })
    }),
    filteredBlocklyFiles: computed(() => {
      const keyword = state.blocklyManagerQuery.value.trim().toLowerCase()
      if (!keyword) return state.blocklyFiles.value
      return state.blocklyFiles.value.filter(item => item.name.toLowerCase().includes(keyword))
    }),
    selectedTask: computed(() => {
      if (!state.selectedTaskId.value) return null
      return state.tasks.value.find(item => item.task_id === state.selectedTaskId.value) || null
    }),
    selectedTaskDetail: computed(() => {
      if (!state.selectedTaskId.value) return null
      return state.taskDetailById.value[state.selectedTaskId.value] || null
    }),
    logCount: computed(() => state.logs.value.length),
  }
}

