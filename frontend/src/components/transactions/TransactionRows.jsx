import { categoryLabel } from '../../lib/labels.js'
import { formatDate } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

// Table of transactions (#14). Rows are the objects api/transactions.js fromApi() returns
// (#17): each carries its `type` (label, sign, tone) and `signedAmount`, so this component
// never maps kinds itself. Each row names its kind in text with a sign symbol
// ("+ Income", "− Expense", "− Transfer out", "+ Transfer in") and the amount carries its
// sign too, so the kind is clear without colour. Colour is only an extra cue.
//
// A row of a type the adapter does not know is shown as "Unknown type (raw value)" with an
// unsigned amount, and a message above the table explains it; the list never crashes.
export default function TransactionRows({ transactions, accountName = (id) => `Account ${id}`, caption }) {
  const unknownMessages = [...new Set(transactions.map((t) => t.type.error).filter(Boolean))]

  return (
    <>
      {unknownMessages.length > 0 && (
        <div className="page-alert" role="status">
          {unknownMessages.map((message) => (
            <p key={message} className="page-alert-message">
              {message}
            </p>
          ))}
        </div>
      )}
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
              const { type } = transaction
              return (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.date)}</td>
                  <td>
                    <span className={`kind-tag kind-${type.tone}`}>
                      {type.sign && (
                        <span className="kind-sign" aria-hidden="true">
                          {type.sign}
                        </span>
                      )}
                      {type.label}
                      {type.raw && <span className="kind-raw">({type.raw})</span>}
                    </span>
                  </td>
                  <td>{accountName(transaction.accountId)}</td>
                  <td>{categoryLabel(transaction.category)}</td>
                  <td>{transaction.note || '—'}</td>
                  <td className={`num amount-${type.tone}`}>
                    {formatEUR(transaction.signedAmount, { signed: Boolean(type.sign) })}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
