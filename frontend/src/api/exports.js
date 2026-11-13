export const TRANSACTION_COLUMNS = [
  'id', 'account_id', 'kind', 'amount', 'currency', 'date', 'category', 'note', 'transfer_id', 'direction',
]

export const EXPORT_FORMATS = Object.freeze({ csv: 'CSV', json: 'JSON', md: 'Markdown' })

export function exportSnapshotReady(results, currentQuery, invalid = false) {
  return !invalid && results.status === 'success' && results.data?.query === currentQuery
}

export function filenameError(filename, format = 'csv') {
  return Object.hasOwn(EXPORT_FORMATS, format) && filename.length <= 100
    && /^[A-Za-z0-9][A-Za-z0-9._ -]*\.(csv|json|md)$/.test(filename)
    && filename.endsWith(`.${format}`)
    ? null
    : `Use a filename ending in .${format}, up to 100 characters, with letters, numbers, spaces, dots, hyphens or underscores.`
}

export function transactionExport(rows, filters) {
  return {
    columns: TRANSACTION_COLUMNS,
    filters: structuredClone(filters),
    rows: rows.map((row) => ({
      id: String(row.id), account_id: String(row.account_id), kind: row.kind,
      amount: row.amount, currency: row.currency ?? 'EUR', date: row.date,
      category: row.category, note: row.note, transfer_id: row.transfer_id ?? '',
      direction: row.direction ?? '',
    })),
  }
}

// Only the money figures and the rate are exported, not counts or other display fields.
const SUMMARY_LABELS = ['income', 'expenses', 'net', 'savingsRate']

export function reportExport(data) {
  return {
    columns: ['month', 'section', 'label', 'value', 'unit'],
    filters: { month: data.month },
    rows: [
      ...SUMMARY_LABELS.map((label) => [label, data.summary[label]]).map(([label, value]) => ({
        month: data.month, section: 'summary', label, value,
        unit: label === 'savingsRate' ? '%' : data.currency,
      })),
      ...data.categories.map((category) => ({
        month: data.month, section: 'category', label: category.name, value: category.total,
        unit: data.currency,
      })),
    ],
  }
}

export async function requestCsv(payload, { signal, fetchImpl = globalThis.fetch } = {}) {
  return requestExport(payload, 'csv', { signal, fetchImpl })
}

export async function requestExport(payload, format, { signal, fetchImpl = globalThis.fetch } = {}) {
  if (!Object.hasOwn(EXPORT_FORMATS, format)) throw new Error('Unsupported export format.')
  const invalid = filenameError(payload.filename, format)
  if (invalid) throw new Error(invalid)
  const response = await fetchImpl(`/api/exports/${format}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal,
  })
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('The export endpoint is unavailable. Restart the backend and try again.')
    }
    const body = await response.json().catch(() => ({}))
    const message = typeof body.detail === 'string' ? body.detail : 'The export could not be downloaded. Check the export settings and try again.'
    throw new Error(message)
  }
  const mediaType = { csv: 'text/csv', json: 'application/json', md: 'text/markdown' }[format]
  if (!response.headers.get('content-type')?.includes(mediaType)) {
    throw new Error('The server returned an unexpected response. Check that the API is running.')
  }
  return response.blob()
}
