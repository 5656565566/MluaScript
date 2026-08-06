let projectModules = []

export function setProjectModuleRegistry(modules) {
  projectModules = Array.isArray(modules) ? modules : []
}

export function getProjectModuleRegistry() {
  return projectModules
}
