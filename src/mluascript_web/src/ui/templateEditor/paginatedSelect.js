export const DEFAULT_SELECT_PAGE_SIZE = 7

function normalizeSearchText(value) {
  return String(value ?? '').trim().toLocaleLowerCase()
}

export function filterSelectOptions(options, query) {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) return [...options]

  return options.filter(option => [option.label, option.value]
    .some(value => normalizeSearchText(value).includes(normalizedQuery)))
}

export function paginateSelectOptions(options, requestedPage, pageSize = DEFAULT_SELECT_PAGE_SIZE) {
  const normalizedPageSize = Math.max(1, Number(pageSize) || DEFAULT_SELECT_PAGE_SIZE)
  const pageCount = Math.max(1, Math.ceil(options.length / normalizedPageSize))
  const page = Math.min(Math.max(1, Number(requestedPage) || 1), pageCount)
  const start = (page - 1) * normalizedPageSize

  return {
    options: options.slice(start, start + normalizedPageSize),
    page,
    pageCount,
    total: options.length,
  }
}
