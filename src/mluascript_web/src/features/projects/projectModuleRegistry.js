let projectModules = []

export function setProjectModuleRegistry(modules) {
  projectModules = Array.isArray(modules) ? modules : []
}

export function getProjectModuleRegistry() {
  return projectModules
}

export function getSelectableProjectModules(currentSource = '') {
  const source = String(currentSource || '').replaceAll('\\', '/')
  return projectModules.filter(module =>
    module.source !== source && Array.isArray(module.exports) && module.exports.length > 0)
}
