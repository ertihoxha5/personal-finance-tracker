import { categoryLabel } from '../../lib/labels.js'
import { formatDate } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'
import { kindDisplay, signedAmount } from '../../lib/transactions.js'

// Table of transactions (#14). Each row names its kind in text with a sign symbol
// ("+ Income", "− Expense", "− Transfer out", "+ Transfer in") and the amount carries
// its sign too, so the kind is clear without colour. Colour is only an extra cue.
export default function TransactionRows({ transactions, accountName = (id) => `Account ${id}`, caption }) {
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Type</th>
            <th scope="col">Account</th>
            <th scope="col">Category</th>
            <th scope="col">Note</th>
            <th scope="col" className="num">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => {
            const kind = kindDisplay(transaction)
            return (
              <tr key={transaction.id}>
                <td>{formatDate(transaction.date)}</td>
                <td>
                  <span className={`kind-tag kind-${kind.tone}`}>
                    {kind.sign && (
                      <span className="kind-sign" aria-hidden="true">
                        {kind.sign}
                      </span>
                    )}
                    {kind.label}
                  </span>
                </td>
                <td>{accountName(transaction.account_id)}</td>
                <td>{categoryLabel(transaction.category)}</td>
                <td>{transaction.note || '—'}</td>
                <td className={`num amount-${kind.tone}`}>{formatEUR(signedAmount(transaction), { signed: true })}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
