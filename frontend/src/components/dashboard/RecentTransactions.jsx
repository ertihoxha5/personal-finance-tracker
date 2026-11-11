import { formatDate } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

export default function RecentTransactions({ transactions }) {
  return (
    <section className="card" aria-labelledby="recent-title">
      <h3 id="recent-title">Recent transactions</h3>
      <div className="table-scroll" role="region" aria-labelledby="recent-title" tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Description</th>
              <th scope="col">Category</th>
              <th scope="col">Account</th>
              <th scope="col" className="num">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((txn) => {
              const isExpense = txn.amount.startsWith('-')
              return (
                <tr key={txn.id}>
                  <td>
                    <time dateTime={txn.date}>{formatDate(txn.date)}</time>
                  </td>
                  <td>{txn.description}</td>
                  <td>{txn.category.name}</td>
                  <td>{txn.account.name}</td>
                  <td className={`num amount ${isExpense ? 'amount-expense' : 'amount-income'}`}>
                    {formatEUR(txn.amount, { signed: true })}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
