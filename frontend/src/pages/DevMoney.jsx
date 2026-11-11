import { useState } from 'react'
import MoneyInput from '../components/MoneyInput.jsx'
import { formatEUR, parseMoneyInput } from '../lib/money.js'

// Development-only demo for #06: shows formatEUR and MoneyInput on fixed examples.
// Registered in App.jsx only when import.meta.env.DEV is true.

const FORMAT_EXAMPLES = ['1250.00', '0.10', '-64.50', '-1250.5', '0.00', '-0.00', '1234567.89']

const INPUT_EXAMPLES = ['12.50', '12,5', '.5', '007', '12.', '', 'abc', '-5', '1,250.00', '12.345']

export default function DevMoney() {
  const [amount, setAmount] = useState(null)

  return (
    <section className="dashboard" aria-labelledby="dev-money-title">
      <h2 id="dev-money-title">Money demo</h2>

      <div className="card">
        <h3>Try the input</h3>
        <MoneyInput
          label="Amount"
          hint="Use a comma or a dot for cents, e.g. 12,50."
          required
          onChange={setAmount}
        />
        <p>
          Emitted value: <code>{amount === null ? 'null' : `"${amount}"`}</code>
          {amount !== null && <> → {formatEUR(amount)}</>}
        </p>
      </div>

      <div className="card">
        <h3>formatEUR</h3>
        <div className="table-scroll" role="region" aria-label="formatEUR examples" tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Input</th>
                <th scope="col" className="num">
                  formatEUR
                </th>
                <th scope="col" className="num">
                  signed
                </th>
              </tr>
            </thead>
            <tbody>
              {FORMAT_EXAMPLES.map((value) => (
                <tr key={value}>
                  <td>
                    <code>"{value}"</code>
                  </td>
                  <td className="num">{formatEUR(value)}</td>
                  <td className="num">{formatEUR(value, { signed: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>parseMoneyInput</h3>
        <div className="table-scroll" role="region" aria-label="parseMoneyInput examples" tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Typed</th>
                <th scope="col">Value</th>
                <th scope="col">Error</th>
              </tr>
            </thead>
            <tbody>
              {INPUT_EXAMPLES.map((text) => {
                const result = parseMoneyInput(text)
                return (
                  <tr key={text}>
                    <td>
                      <code>"{text}"</code>
                    </td>
                    <td>
                      <code>{result.value === null ? 'null' : `"${result.value}"`}</code>
                    </td>
                    <td>{result.error ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
