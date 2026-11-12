// Client-side form rules (#12). They mirror the Python validators (PositiveAmount,
// NonEmptyText) so most mistakes are caught before a request is sent; the server
// still validates everything and its errors are shown the same way.
//
// Each rule takes the raw value and returns an error message, or null when valid.
// Amounts stay strings throughout: no parseFloat, no Number(), so "0.10" can never
// turn into 0.1000000001 on the way.

import { parseMoneyInput } from './money.js'

export const REQUIRED_MESSAGE = 'This field is required.'
export const POSITIVE_MESSAGE = 'Enter an amount greater than zero.'
export const AMOUNT_REQUIRED_MESSAGE = 'Enter an amount.'

const ZERO_AMOUNT = /^0\.00$/

// required("  ") -> 'This field is required.'; required("Rent") -> null.
// Strings are trimmed, matching NonEmptyText, which strips before checking.
export function required(value, message = REQUIRED_MESSAGE) {
  if (value === null || value === undefined) return message
  if (typeof value === 'string' && value.trim() === '') return message
  return null
}

// positiveDecimal("12,50") -> null; "0", "-5", "abc", "1.234" -> a message.
// Uses the same pattern as MoneyInput (#06) and rejects zero by comparing the
// normalised string, so the check never goes through floating point.
export function positiveDecimal(text) {
  if (typeof text !== 'string' || text.trim() === '') return AMOUNT_REQUIRED_MESSAGE
  const { value, error } = parseMoneyInput(text)
  if (error !== null) return error
  if (ZERO_AMOUNT.test(value)) return POSITIVE_MESSAGE
  return null
}

// Run a { field: rule | [rules] } map over a values object and return
// { field: firstMessage } for the fields that fail. Field order is kept, so the
// first key is the first invalid field on screen.
export function validateFields(values, rules) {
  const errors = {}
  for (const [field, fieldRules] of Object.entries(rules)) {
    for (const rule of [fieldRules].flat()) {
      // Only the value is passed: required(value, message) takes a custom message second.
      const message = rule(values[field])
      if (message) {
        errors[field] = message
        break
      }
    }
  }
  return errors
}
