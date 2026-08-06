import { setProjectModuleRegistry } from './projectModuleRegistry.js'

export function createProjectActions({ state, projectApi, compileBlocklyXml, getActions }) {
  let projectSaveQueue = Promise.resolve()

  function projectKey() {
    return state.currentProject.value?.key || ''
  }

  function collectProjectFiles(items, output = []) {
    for (const item of items || []) {
      if (item?.kind === 'file' && item.path) output.push(String(item.path).replaceAll('\\', '/'))
      if (Array.isArray(item?.children)) collectProjectFiles(item.children, output)
    }
    return output
  }

  function blocklyScriptPath(path) {
    const normalized = String(path || '').replaceAll('\\', '/')
    if (!normalized.startsWith('blockly/') || !normalized.toLowerCase().endsWith('.xml')) {
      throw new Error(`Blockly 调试文件路径无效: ${normalized}`)
    }
    return `scripts/${normalized.slice('blockly/'.length, -'.xml'.length)}.lua`
  }

  async function readProjectText(path) {
    const tab = openFileByPath(path)
    if (tab?.file?.encoding === 'utf-8') return String(tab.content ?? '')
    const file = await projectApi.readFile(projectKey(), path)
    if (file.encoding !== 'utf-8') throw new Error(`调试文件不是文本文件: ${path}`)
    return String(file.content ?? '')
  }

  async function buildDebugSnapshot(entryPath) {
    const projectType = state.currentProject.value?.project_type || ''
    const primaryPath = state.currentProject.value?.primary_path || ''
    const resolvedEntry = String(entryPath || primaryPath).replaceAll('\\', '/')
    if (projectType === 'maa') return { mode: 'pipeline', entryPath: resolvedEntry }

    if (projectType === 'lua-file') {
      return { mode: 'script', entryPath: primaryPath, luaCode: await readProjectText(primaryPath), sourceOverrides: {} }
    }
    if (projectType === 'blockly-file') {
      const compiled = compileBlocklyXml(await readProjectText(primaryPath))
      if (compiled.stale || compiled.diagnostics.length) {
        throw new Error(compiled.diagnostics[0]?.message || 'Blockly 调试编译失败')
      }
      return { mode: 'script', entryPath: `${primaryPath.slice(0, -4)}.lua`, luaCode: compiled.code, sourceOverrides: {} }
    }

    const files = collectProjectFiles(state.projectTree.value)
    const sourceOverrides = {}
    for (const path of files.filter(item => item.startsWith('scripts/') && item.toLowerCase().endsWith('.lua'))) {
      sourceOverrides[path] = await readProjectText(path)
    }
    if (projectType === 'blockly-package') {
      for (const path of files.filter(item => item.startsWith('blockly/') && item.toLowerCase().endsWith('.xml'))) {
        const scriptPath = blocklyScriptPath(path)
        if (Object.hasOwn(sourceOverrides, scriptPath)) {
          throw new Error(`Blockly 生成 Lua 与手写文件冲突: ${scriptPath}`)
        }
        const compiled = compileBlocklyXml(await readProjectText(path))
        if (compiled.stale || compiled.diagnostics.length) {
          throw new Error(`${path}: ${compiled.diagnostics[0]?.message || 'Blockly 调试编译失败'}`)
        }
        sourceOverrides[scriptPath] = compiled.code
      }
    }
    const virtualEntry = resolvedEntry.startsWith('blockly/') ? blocklyScriptPath(resolvedEntry) : resolvedEntry
    if (!virtualEntry.startsWith('scripts/') || !virtualEntry.toLowerCase().endsWith('.lua')) {
      throw new Error('调试入口必须是 scripts/ 下的 Lua 或 blockly/ 下的 Blockly 文件')
    }
    if (!Object.hasOwn(sourceOverrides, virtualEntry)) throw new Error(`调试入口不存在: ${virtualEntry}`)
    return {
      mode: 'script',
      entryPath: virtualEntry,
      luaCode: sourceOverrides[virtualEntry],
      sourceOverrides,
    }
  }

  function resetOpenFiles() {
    state.projectOpenFiles.value = []
    state.projectSelectedPath.value = ''
    state.projectFile.value = null
    state.projectFileContent.value = ''
    state.projectFileDirty.value = false
    state.projectGeneratedLua.value = ''
    state.projectGeneratedLuaStale.value = false
    state.projectBlocklyDiagnostics.value = []
    state.projectLuaPreviewVisible.value = false
    if (state.projectModules) state.projectModules.value = []
    setProjectModuleRegistry([])
  }

  function openFileByPath(path) {
    return state.projectOpenFiles.value.find(tab => tab.path === path) || null
  }

  function captureActiveFile() {
    const tab = openFileByPath(state.projectSelectedPath.value)
    if (!tab) return null
    tab.file = state.projectFile.value
    tab.content = state.projectFileContent.value
    tab.dirty = state.projectFileDirty.value
    tab.generatedLua = state.projectGeneratedLua.value
    tab.generatedLuaStale = state.projectGeneratedLuaStale.value
    tab.blocklyDiagnostics = state.projectBlocklyDiagnostics.value
    return tab
  }

  function activateOpenFile(tab) {
    state.projectSelectedPath.value = tab?.path || ''
    state.projectFile.value = tab?.file || null
    state.projectFileContent.value = tab?.content || ''
    state.projectFileDirty.value = Boolean(tab?.dirty)
    state.projectGeneratedLua.value = tab?.generatedLua || ''
    state.projectGeneratedLuaStale.value = Boolean(tab?.generatedLuaStale)
    state.projectBlocklyDiagnostics.value = tab?.blocklyDiagnostics || []
    state.projectLuaPreviewVisible.value = false
  }

  function remapPath(path, sourcePath, targetPath) {
    if (path === sourcePath) return targetPath
    if (path.startsWith(`${sourcePath}/`)) return `${targetPath}${path.slice(sourcePath.length)}`
    return path
  }

  function applyProjectPathChange(sourcePath, targetPath) {
    const selectedTargetPath = remapPath(state.projectSelectedPath.value, sourcePath, targetPath)
    for (const tab of state.projectOpenFiles.value) {
      const remapped = remapPath(tab.path, sourcePath, targetPath)
      if (remapped === tab.path) continue
      tab.path = remapped
      if (tab.file) {
        tab.file = {
          ...tab.file,
          path: remapped,
          name: remapped.split('/').pop() || tab.file.name,
        }
      }
    }
    if (state.currentProject.value?.primary_path) {
      state.currentProject.value = {
        ...state.currentProject.value,
        primary_path: remapPath(state.currentProject.value.primary_path, sourcePath, targetPath),
      }
    }
    const manifest = state.currentManifest.value
    if (manifest) {
      for (const entrypoint of Object.values(manifest.entrypoints || {})) {
        for (const field of ['script', 'blockly', 'maa', 'template']) {
          if (entrypoint?.[field]) entrypoint[field] = remapPath(entrypoint[field], sourcePath, targetPath)
        }
        for (const [name, path] of Object.entries(entrypoint?.models || {})) {
          entrypoint.models[name] = remapPath(path, sourcePath, targetPath)
        }
      }
      for (const [name, path] of Object.entries(manifest.resources || {})) {
        manifest.resources[name] = remapPath(path, sourcePath, targetPath)
      }
      for (const model of Object.values(manifest.models || {})) {
        if (model?.path) model.path = remapPath(model.path, sourcePath, targetPath)
      }
    }
    const selected = state.projectOpenFiles.value.find(tab => tab.path === selectedTargetPath)
    if (selected) activateOpenFile(selected)
  }

  return {
    async loadProjects() {
      state.projectLoading.value = true
      try {
        const data = await projectApi.listProjects()
        state.projects.value = Array.isArray(data.items) ? data.items : []
        return state.projects.value
      } finally {
        state.projectLoading.value = false
      }
    },

    async createProject(payload) {
      const data = await projectApi.createProject(payload)
      await getActions().loadProjects()
      await getActions().openProject(data.key)
      getActions().setStatus(`项目已创建: ${data.name}`, 'success')
      return data
    },

    async updateProjectInfo(payload) {
      const activeProjectKey = projectKey()
      if (!activeProjectKey) return null
      const data = await projectApi.updateProject(activeProjectKey, payload)
      if (projectKey() === activeProjectKey) {
        state.currentProject.value = data
        state.currentManifest.value = {
          ...state.currentManifest.value,
          package: {
            ...(state.currentManifest.value?.package || {}),
            id: data.package_id,
            name: data.name,
            version: data.version,
            author: data.author || '',
            description: data.description || '',
          },
        }
      }
      await getActions().loadProjects()
      getActions().setStatus('项目信息已更新', 'success')
      return data
    },

    async openProject(key) {
      state.projectLoading.value = true
      try {
        const data = await projectApi.openProject(key)
        state.currentProject.value = data.project || null
        state.currentManifest.value = data.manifest || null
        state.projectTree.value = Array.isArray(data.tree) ? data.tree : []
        resetOpenFiles()
        if (state.projectModules && typeof projectApi.listModules === 'function') {
          const moduleData = await projectApi.listModules(data.project?.key || key)
          state.projectModules.value = Array.isArray(moduleData.modules) ? moduleData.modules : []
          setProjectModuleRegistry(state.projectModules.value)
        }
        state.projectDiagnostics.value = data.project?.diagnostics || []
        const primaryPath = data.project?.primary_path || ''
        const primaryFile = state.projectTree.value.find(item => item.kind === 'file' && item.path === primaryPath)
        if (primaryFile) await getActions().selectProjectFile(primaryFile)
        return data
      } finally {
        state.projectLoading.value = false
      }
    },

    closeProject() {
      state.currentProject.value = null
      state.currentManifest.value = null
      state.projectTree.value = []
      resetOpenFiles()
      state.projectDiagnostics.value = []
    },

    async selectProjectFile(item) {
      if (!item || item.kind !== 'file' || !projectKey()) return null
      captureActiveFile()
      const existingTab = openFileByPath(item.path)
      if (existingTab) {
        activateOpenFile(existingTab)
        return existingTab.file
      }

      const data = await projectApi.readFile(projectKey(), item.path)
      const tab = {
        path: item.path,
        file: data,
        content: data.content ?? '',
        dirty: false,
        generatedLua: '',
        generatedLuaStale: false,
        blocklyDiagnostics: [],
      }
      state.projectOpenFiles.value.push(tab)
      activateOpenFile(tab)
      return data
    },

    closeProjectFile(path) {
      captureActiveFile()
      const index = state.projectOpenFiles.value.findIndex(tab => tab.path === path)
      if (index < 0) return false
      const wasActive = state.projectSelectedPath.value === path
      state.projectOpenFiles.value.splice(index, 1)
      if (wasActive) {
        const nextTab = state.projectOpenFiles.value[Math.min(index, state.projectOpenFiles.value.length - 1)] || null
        activateOpenFile(nextTab)
      }
      return true
    },

    setProjectFileContent(content) {
      state.projectFileContent.value = content
      state.projectFileDirty.value = true
      captureActiveFile()
    },

    setProjectGeneratedLua(code, diagnostics = [], stale = false) {
      state.projectGeneratedLua.value = code || ''
      state.projectGeneratedLuaStale.value = Boolean(stale)
      state.projectBlocklyDiagnostics.value = Array.isArray(diagnostics) ? diagnostics : []
      captureActiveFile()
    },

    discardProjectFileChanges() {
      state.projectFileContent.value = state.projectFile.value?.content ?? ''
      state.projectFileDirty.value = false
      captureActiveFile()
    },

    saveProjectFile({ path = state.projectSelectedPath.value, notify = true } = {}) {
      const save = async () => {
        captureActiveFile()
        const tab = openFileByPath(path)
        const file = tab?.file
        const activeProjectKey = projectKey()
        if (!tab || !file || !activeProjectKey || file.encoding !== 'utf-8') return null
        if (!tab.dirty) {
          if (notify) getActions().setStatus(`已保存 ${file.path}`, 'success')
          return file
        }

        const contentSnapshot = tab.content
        const pathSnapshot = file.path
        const data = await projectApi.writeFile(activeProjectKey, {
          path: pathSnapshot,
          content: contentSnapshot,
          expectedMtime: file.mtime,
        })

        // 保存完成期间用户可能切换标签或继续编辑，mtime 必须推进，但不能用旧响应覆盖新草稿。
        if (projectKey() === activeProjectKey) {
          if (state.projectSelectedPath.value === pathSnapshot) captureActiveFile()
          const currentTab = openFileByPath(pathSnapshot)
          if (currentTab) {
            currentTab.file = data
            if (currentTab.content === contentSnapshot) {
              currentTab.content = data.content ?? ''
              currentTab.dirty = false
            } else {
              currentTab.dirty = true
            }
          }
          if (state.projectSelectedPath.value === pathSnapshot && currentTab) {
            activateOpenFile(currentTab)
          }
          await getActions().reloadProjectTree()
          if (notify) getActions().setStatus(`已保存 ${data.path}`, 'success')
        }
        return data
      }

      const result = projectSaveQueue.then(save, save)
      projectSaveQueue = result.catch(() => null)
      return result
    },

    async saveAllProjectFiles() {
      captureActiveFile()
      const dirtyPaths = state.projectOpenFiles.value.filter(tab => tab.dirty).map(tab => tab.path)
      for (const path of dirtyPaths) {
        await getActions().saveProjectFile({ path, notify: false })
      }
      return dirtyPaths.length
    },

    async createProjectFile(path, content = '') {
      if (!projectKey()) return null
      state.projectFileOperationLoading.value = true
      try {
        const data = await projectApi.createFile(projectKey(), { path, content })
        await getActions().reloadProjectTree()
        getActions().setStatus(`已创建 ${data.path}`, 'success')
        return data
      } finally {
        state.projectFileOperationLoading.value = false
      }
    },

    async deleteProjectFile(path) {
      if (!projectKey() || !path) return null
      state.projectFileOperationLoading.value = true
      try {
        const data = await projectApi.deleteFile(projectKey(), path)
        getActions().closeProjectFile(path)
        await getActions().reloadProjectTree()
        getActions().setStatus(`已删除 ${data.path}`, 'success')
        return data
      } finally {
        state.projectFileOperationLoading.value = false
      }
    },

    async createProjectDirectory(path) {
      if (!projectKey()) return null
      state.projectFileOperationLoading.value = true
      try {
        const data = await projectApi.createDirectory(projectKey(), { path })
        await getActions().reloadProjectTree()
        getActions().setStatus(`已创建目录 ${data.path}`, 'success')
        return data
      } finally {
        state.projectFileOperationLoading.value = false
      }
    },

    renameProjectPath(path, newName) {
      const rename = async () => {
        const activeProjectKey = projectKey()
        if (!activeProjectKey) return null
        captureActiveFile()
        state.projectFileOperationLoading.value = true
        try {
          const data = await projectApi.renamePath(activeProjectKey, { path, newName })
          const targetPath = data.path
          applyProjectPathChange(path, targetPath)
          await getActions().reloadProjectTree()
          getActions().setStatus(`已重命名为 ${targetPath}`, 'success')
          return data
        } finally {
          state.projectFileOperationLoading.value = false
        }
      }

      const result = projectSaveQueue.then(rename, rename)
      projectSaveQueue = result.catch(() => null)
      return result
    },

    moveProjectPath(sourcePath, destinationPath) {
      const move = async () => {
        const activeProjectKey = projectKey()
        if (!activeProjectKey) return null
        captureActiveFile()
        state.projectFileOperationLoading.value = true
        try {
          const data = await projectApi.movePath(activeProjectKey, { sourcePath, destinationPath })
          applyProjectPathChange(sourcePath, data.path)
          await getActions().reloadProjectTree()
          getActions().setStatus(`已移动到 ${data.path}`, 'success')
          return data
        } finally {
          state.projectFileOperationLoading.value = false
        }
      }

      const result = projectSaveQueue.then(move, move)
      projectSaveQueue = result.catch(() => null)
      return result
    },

    async uploadProjectFile(path, file) {
      if (!projectKey() || !file) return null
      state.projectFileOperationLoading.value = true
      try {
        const data = await projectApi.uploadFile(projectKey(), path, file)
        await getActions().reloadProjectTree()
        getActions().setStatus(`已上传 ${data.path}`, 'success')
        return data
      } finally {
        state.projectFileOperationLoading.value = false
      }
    },

    projectFileDownloadUrl(path) {
      return projectKey() && path ? projectApi.fileDownloadUrl(projectKey(), path) : ''
    },

    async reloadProjectTree() {
      if (!projectKey()) return []
      const data = await projectApi.listTree(projectKey())
      state.projectTree.value = Array.isArray(data.items) ? data.items : []
      if (state.projectModules && typeof projectApi.listModules === 'function') {
        const moduleData = await projectApi.listModules(projectKey())
        state.projectModules.value = Array.isArray(moduleData.modules) ? moduleData.modules : []
        setProjectModuleRegistry(state.projectModules.value)
      }
      return state.projectTree.value
    },

    async validateProject() {
      if (!projectKey()) return null
      const data = await projectApi.validate(projectKey())
      state.projectDiagnostics.value = Array.isArray(data.diagnostics) ? data.diagnostics : []
      getActions().setStatus(data.valid ? '项目校验通过' : '项目校验发现问题', data.valid ? 'success' : 'warning')
      return data
    },

    async buildProject({ generatedModules = null } = {}) {
      if (!projectKey()) return null
      await getActions().saveAllProjectFiles()
      const projectType = state.currentProject.value?.project_type || ''
      const payload = {}
      if (projectType === 'blockly-package' && generatedModules) {
        payload.generatedModules = generatedModules
      } else if (projectType === 'blockly-package' || projectType === 'blockly-file') {
        const primaryPath = state.currentProject.value?.primary_path || ''
        if (state.projectSelectedPath.value !== primaryPath) {
          throw new Error('请先打开 Blockly 主入口，再生成分发产物')
        }
        if (state.projectGeneratedLuaStale.value || state.projectBlocklyDiagnostics.value.length) {
          throw new Error('Blockly 存在错误，无法生成分发产物')
        }
        payload.generatedLua = state.projectGeneratedLua.value
        payload.generatedFrom = state.projectSelectedPath.value
      }
      state.projectBuildLoading.value = true
      try {
        const data = await projectApi.build(projectKey(), payload)
        state.projectBuildResult.value = data
        getActions().setStatus(`已生成 ${data.filename}`, 'success')
        return data
      } finally {
        state.projectBuildLoading.value = false
      }
    },

    async debugProject({ mode = 'script', entryPath = '', templatePayload = null } = {}) {
      const activeProjectKey = projectKey()
      if (!activeProjectKey) throw new Error('请先打开项目')
      await getActions().saveAllProjectFiles()
      const snapshot = await buildDebugSnapshot(entryPath)
      const payload = {
        ...snapshot,
        mode: mode === 'template' ? 'template' : snapshot.mode,
        sessionLabel: state.selectedSession.value || '',
      }
      if (templatePayload) {
        payload.templateMode = templatePayload.mode || ''
        payload.workflowKey = templatePayload.workflowKey || ''
        payload.workflow = templatePayload.workflow || {}
        payload.runtime = templatePayload.runtime || {}
      }
      state.projectDebugLoading.value = true
      try {
        const data = await projectApi.debug(activeProjectKey, payload)
        state.projectDebugTaskByKey.value = {
          ...state.projectDebugTaskByKey.value,
          [activeProjectKey]: data,
        }
        // 调试启动只会改变任务状态，不重载编辑器、日志和全局 SSE。
        await getActions().refreshTaskManagerData()
        getActions().setStatus(`调试任务已启动: ${data.taskId}`, 'success')
        return data
      } finally {
        state.projectDebugLoading.value = false
      }
    },
  }
}
