// Synthetic API error bodies in the { code, message, field } shape that
// pft FinanceError.to_dict() produces. Used by tests and the /dev/errors demo
// until the real endpoints exist.

export const FIELD_ERROR = {
  code: 'invalid_amount',
  message: 'enter an amount greater than zero',
  field: 'amount',
}

export const CATEGORY_ERROR = {
  code: 'invalid_category',
  message:
    "unknown category 'groceries'; choose one of: salary, food, rent, bills, transport, fun, health, education, other",
  field: 'category',
}

export const PAGE_ERROR = {
  code: 'account_not_found',
  message: 'that account no longer exists; refresh the list',
  field: null,
}

export const SERVER_ERROR = { status: 500, message: '' }

export const MULTIPLE_ERRORS = { errors: [FIELD_ERROR, CATEGORY_ERROR, PAGE_ERROR] }
