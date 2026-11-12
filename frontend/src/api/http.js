// Shared fetch helper for the API clients (#18, #19). Failures reject with an ApiError that
// carries the server's message, the input field it belongs to (or null), the HTTP status and
// the stable error code, so every screen can show them the same way.

export class ApiError extends Error {
  constructor(message, { field = null, status = 400, code = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.field = field
    this.status = status
    this.code = code
  }
}

// Server field names -> the names the forms use.
const FIELD_NAMES = { opening_balance: 'openingBalance', account_id: 'accountId' }

export async function request(path, { method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('The server could not be reached. Check that the API is running.', { status: 0 })
  }

  let payload = null
  try {
    payload = await response.json()
  } catch {
    // A non-JSON body (a proxy error page) is reported with the generic message below.
  }

  if (!response.ok) {
    const field = payload?.field ?? null
    throw new ApiError(payload?.message ?? 'The server could not complete that request.', {
      field: FIELD_NAMES[field] ?? field,
      status: response.status,
      code: payload?.code ?? null,
    })
  }
  return payload
}
