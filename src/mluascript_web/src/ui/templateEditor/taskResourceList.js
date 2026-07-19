export const TASK_RESOURCE_PAGE_SIZE = 4

function normalizeSearchText(value) {
  return String(value ?? '').trim().toLocaleLowerCase()
}

export function filterTaskDefinitions(tasks, query) {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) return [...tasks]

  return tasks.filter(task => [task.k, task.t, task.fn]
    .some(value => normalizeSearchText(value).includes(normalizedQuery)))
}
