const ARTIFACT_TYPE_LABELS = {
  'lua-package': 'Lua 可打包项目',
  'blockly-package': 'Blockly 可打包项目',
  maa: 'Maa 自动化项目',
  'lua-file': 'Lua 单文件',
  'blockly-file': 'Blockly 单文件',
  package: '脚本包',
  lua: 'Lua 脚本',
  pipeline: 'Pipeline',
}

export function artifactTypeKey(artifact) {
  return String(artifact?.project_type || artifact?._kind || artifact?.kind || 'lua')
}

export function artifactTypeLabel(artifact) {
  const key = artifactTypeKey(artifact)
  return ARTIFACT_TYPE_LABELS[key] || key
}

export function artifactTypeClass(artifact) {
  const key = artifactTypeKey(artifact)
  if (key === 'maa' || key === 'pipeline') return 'task-kind-pipeline'
  return 'task-kind-lua'
}
