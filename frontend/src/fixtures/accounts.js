// Synthetic data for the Accounts screen. Amounts are decimal strings, signed on
// transactions (expense < 0). Shapes match what the accounts API will return.

export const ACCOUNT_TYPES = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank', label: 'Bank' },
  { value: 'card', label: 'Card' },
  { value: 'savings', label: 'Savings' },
]

export const ACCOUNT_SEED = {
  accounts: [
    { id: 1, name: 'Checking', type: 'bank', openingBalance: '1500.00' },
    { id: 2, name: 'Savings', type: 'savings', openingBalance: '5000.00' },
    { id: 3, name: 'Wallet', type: 'cash', openingBalance: '120.00' },
    { id: 4, name: 'Visa', type: 'card', openingBalance: '0.00' },
  ],
  transactions: [
    { id: 101, accountId: 1, date: '2026-11-01', description: 'Salary', kind: 'income', amount: '2200.00' },
    { id: 102, accountId: 1, date: '2026-11-02', description: 'Groceries', kind: 'expense', amount: '-64.50' },
    { id: 103, accountId: 1, date: '2026-11-03', description: 'Rent', kind: 'expense', amount: '-600.00' },
    // A transfer is two legs that share transferId; editing one updates both.
    { id: 104, accountId: 1, date: '2026-11-05', description: 'Move to savings', kind: 'transfer', amount: '-300.00', transferId: 'tr-1', counterpartId: 105 },
    { id: 105, accountId: 2, date: '2026-11-05', description: 'Move to savings', kind: 'transfer', amount: '300.00', transferId: 'tr-1', counterpartId: 104 },
    { id: 106, accountId: 4, date: '2026-11-06', description: 'Coffee beans', kind: 'expense', amount: '-18.90' },
  ],
}

export const KIND_LABELS = { income: 'Income', expense: 'Expense', transfer: 'Transfer' }
