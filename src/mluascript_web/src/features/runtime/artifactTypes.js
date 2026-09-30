const ARTIFACT_TYPE_LABELS = {
  'lua-package': '脚本包',
  'blockly-package': '脚本包',
  maa: '脚本包',
  'lua-file': '单文件',
  'blockly-file': '单文件',
  package: '脚本包',
  lua: '单文件',
  pipeline: '脚本包',
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

export function matchesResourceQuery(resource, query) {
  const normalized = String(query || '').trim().toLocaleLowerCase()
  if (!normalized) return true
  return [
    resource?.name,
    resource?.path,
    resource?.description,
    resource?.author,
    resource?.version,
    resource?.package_id,
    resource?.entrypoint,
  ].some(value => String(value || '').toLocaleLowerCase().includes(normalized))
}
