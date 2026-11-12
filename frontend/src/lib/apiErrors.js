// Turns an API failure into what the screen shows (#10).
//
// The API reports domain errors as { code, message, field } (pft FinanceError.to_dict()).
// An error with a field belongs under that input; anything else (no field, a network
// failure, an unexpected value) goes to one page alert the user can retry or dismiss.
//
// mapApiError accepts:
//   - one error body { code, message, field }, a list of them, or { errors: [...] };
//   - an ApiError (or any Error) carrying message and optionally code, field, status;
//   - a TypeError from fetch(), which is how browsers report a network failure.
// It returns { fieldErrors: { [field]: message }, pageAlert: null | { code, message, retryable } }.

export const NETWORK_MESSAGE = 'The server could not be reached. Check that the API is running and try again.'
export const UNKNOWN_MESSAGE = 'Something went wrong. Try again in a moment.'
export const SERVER_MESSAGE = 'The server could not complete that request. Nothing was changed.'

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1)

function readable(message) {
  if (typeof message !== 'string' || message.trim() === '') return null
  return capitalise(message.trim())
}

function toList(error) {
  if (Array.isArray(error)) return error
  if (error && typeof error === 'object' && Array.isArray(error.errors)) return error.errors
  return [error]
}

function pageAlertFor(item) {
  if (item instanceof TypeError) {
    return { code: 'network_error', message: NETWORK_MESSAGE, retryable: true }
  }
  if (!item || typeof item !== 'object') {
    return { code: 'unknown_error', message: UNKNOWN_MESSAGE, retryable: true }
  }
  const status = Number(item.status) || null
  if (status !== null && status >= 500) {
    return { code: item.code ?? 'server_error', message: readable(item.message) ?? SERVER_MESSAGE, retryable: true }
  }
  const message = readable(item.message)
  if (message === null) return { code: item.code ?? 'unknown_error', message: UNKNOWN_MESSAGE, retryable: true }
  // A 4xx domain error (e.g. account_not_found) will fail the same way again, so no retry.
  return { code: item.code ?? 'unknown_error', message, retryable: status === null && !item.code }
}

export function mapApiError(error) {
  const result = { fieldErrors: {}, pageAlert: null }
  if (error === null || error === undefined) return result

  for (const item of toList(error)) {
    const field = item && typeof item === 'object' && typeof item.field === 'string' ? item.field : null
    const message = item && typeof item === 'object' ? readable(item.message) : null
    if (field && message && !(item instanceof TypeError)) {
      // The first message for a field wins; the user fixes one thing at a time.
      result.fieldErrors[field] ??= message
    } else if (result.pageAlert === null) {
      result.pageAlert = pageAlertFor(item)
    }
  }
  return result
}
