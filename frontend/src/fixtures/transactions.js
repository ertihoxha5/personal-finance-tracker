// Independent synthetic preview for #08, following #14's planned field names.
// Amount is an unsigned decimal string; transfer direction supplies its sign.
export const FILTER_ACCOUNTS = [
  { id: 1, name: 'Checking' },
  { id: 2, name: 'Savings' },
  { id: 3, name: 'Wallet' },
]

export const FILTER_CATEGORIES = ['Food', 'Housing', 'Transport', 'Salary', 'Other']
export const FILTER_KINDS = ['income', 'expense', 'transfer']

export const FILTER_TRANSACTIONS = [
  { id: 201, account_id: 1, date: '2026-11-01', category: 'Salary', kind: 'income', amount: '2200.00', note: 'Monthly salary' },
  { id: 202, account_id: 1, date: '2026-11-02', category: 'Food', kind: 'expense', amount: '64.50', note: 'Weekly groceries' },
  { id: 203, account_id: 1, date: '2026-11-03', category: 'Housing', kind: 'expense', amount: '600.00', note: 'November rent' },
  { id: 204, account_id: 1, date: '2026-11-05', category: 'Other', kind: 'transfer', direction: 'out', amount: '300.00', note: 'Move to savings' },
  { id: 205, account_id: 2, date: '2026-11-05', category: 'Other', kind: 'transfer', direction: 'in', amount: '300.00', note: 'Move to savings' },
  { id: 206, account_id: 3, date: '2026-11-10', category: 'Food', kind: 'expense', amount: '12.50', note: 'Lunch with classmates' },
  { id: 207, account_id: 3, date: '2026-11-15', category: 'Food', kind: 'expense', amount: '25.00', note: 'Study group dinner' },
  { id: 208, account_id: 1, date: '2026-11-30', category: 'Transport', kind: 'expense', amount: '20.00', note: 'Bus pass' },
  { id: 209, account_id: 1, date: '2026-10-31', category: 'Food', kind: 'expense', amount: '20.00', note: 'Groceries before November' },
  { id: 210, account_id: 1, date: '2026-12-01', category: 'Food', kind: 'expense', amount: '20.01', note: 'December groceries' },
]
