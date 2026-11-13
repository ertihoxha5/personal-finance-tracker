import { positiveDecimal, required, validateFields } from './validation.js'

// Client-side checks for the Transfer form (#23). They mirror Ledger.transfer so the user
// hears about a mistake before the request is sent; the server checks everything again,
// including the source balance, which only the server knows for sure.
export const SAME_ACCOUNT_MESSAGE = 'Choose two different accounts.'

export function validateTransfer(values) {
  const errors = validateFields(values, {
    fromAccountId: (v) => required(v, 'Choose the account the money leaves.'),
    toAccountId: (v) => required(v, 'Choose the account the money goes to.'),
    amount: positiveDecimal,
    date: (v) => required(v, 'Choose a date.'),
  })
  if (!errors.toAccountId && values.fromAccountId && String(values.fromAccountId) === String(values.toAccountId)) {
    errors.toAccountId = SAME_ACCOUNT_MESSAGE
  }
  return errors
}
