export const TRANSACTION_COLUMNS = [
  'id', 'account_id', 'kind', 'amount', 'currency', 'date', 'category', 'note', 'transfer_id', 'direction',
]

export function filenameError(filename) {
  return filename.length <= 100 && /^[A-Za-z0-9][A-Za-z0-9._ -]*\.csv$/.test(filename)
    ? null
    : 'Use a filename ending in .csv, up to 100 characters, with letters, numbers, spaces, dots, hyphens or underscores.'
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

export function reportExport(data) {
  return {
    columns: ['month', 'section', 'label', 'value', 'unit'],
    filters: { month: data.month },
    rows: [
      ...Object.entries(data.summary).map(([label, value]) => ({
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
  const invalid = filenameError(payload.filename)
  if (invalid) throw new Error(invalid)
  const response = await fetchImpl('/api/exports/csv', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message = typeof body.detail === 'string' ? body.detail : 'The CSV could not be downloaded. Check the export settings and try again.'
    throw new Error(message)
  }
  if (!response.headers.get('content-type')?.includes('text/csv')) {
    throw new Error('The server returned an unexpected response. Check that the API is running.')
  }
  return response.blob()
}
