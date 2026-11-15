import { ApiError, request } from './http.js'

export const MAX_CSV_SIZE = 1_000_000
export const fetchOptionalFeatures = () => request('/optional/features')
export const optionalEnabled = (features) => ['undo', 'import', 'charts'].some((name) => features?.[name] === true)
export const startHistory = () => request('/optional/history', { method: 'POST' })
export const readHistory = (token) => request(`/optional/history/${encodeURIComponent(token)}`)
export const historyAction = (token, body) => request(`/optional/history/${encodeURIComponent(token)}`, { method: 'POST', body })
export const previewImport = (accountId, csvText) => request('/optional/import/preview', {
  method: 'POST', body: { account_id: Number(accountId), csv_text: csvText },
})

export function importCanConfirm(preview, accountId, csvText) {
  return Boolean(preview?.revision && preview.accepted?.length > 0
    && preview.accountId === String(accountId) && preview.csvText === csvText)
}

export function confirmImport(preview, accountId, csvText) {
  if (!importCanConfirm(preview, accountId, csvText)) throw new Error('Preview this CSV and account before importing.')
  return request('/optional/import/confirm', {
    method: 'POST', body: { account_id: Number(accountId), csv_text: csvText, expected_revision: preview.revision },
  })
}

export function csvFileError(file) {
  if (!file || !file.name.toLowerCase().endsWith('.csv')) return 'Choose a UTF-8 CSV file.'
  if (file.size > MAX_CSV_SIZE) return 'Choose a CSV file smaller than 1 MB.'
  return null
}

export async function requestChart(kind, filters, { fetchImpl = globalThis.fetch } = {}) {
  if (!['categories', 'trend'].includes(kind)) throw new Error('Unsupported chart type.')
  const query = new URLSearchParams(kind === 'categories'
    ? { start: filters.start, end: filters.end }
    : { end: filters.end, months: String(filters.months) })
  const response = await fetchImpl(`/api/optional/charts/${kind}?${query}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body.message ?? body.detail ?? 'The PNG could not be downloaded.', { status: response.status })
  }
  if (!response.headers.get('content-type')?.includes('image/png')) throw new Error('The server did not return a PNG chart.')
  return response.blob()
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  try { link.click() } finally {
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
