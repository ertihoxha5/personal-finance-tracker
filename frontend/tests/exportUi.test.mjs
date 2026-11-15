import assert from 'node:assert/strict'
import { after, afterEach, test } from 'node:test'
import { createRequire, Module } from 'node:module'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildSync } from 'esbuild'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const { render, screen, fireEvent, waitFor, cleanup } = await import('@testing-library/react')
const originalFetch = globalThis.fetch
const originalClick = dom.window.HTMLAnchorElement.prototype.click
dom.window.HTMLAnchorElement.prototype.click = () => {}
afterEach(() => { cleanup(); globalThis.fetch = originalFetch })
after(() => { dom.window.HTMLAnchorElement.prototype.click = originalClick; dom.window.close() })

function component(path) {
  const filename = fileURLToPath(import.meta.url)
  const { outputFiles } = buildSync({
    entryPoints: [fileURLToPath(new URL(path, import.meta.url))], bundle: true,
    write: false, platform: 'node', format: 'cjs', packages: 'external',
    jsx: 'automatic', loader: { '.css': 'empty' },
  })
  const loaded = new Module(filename)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(dirname(filename))
  loaded.require = createRequire(import.meta.url)
  loaded._compile(outputFiles[0].text, filename)
  return loaded.exports.default
}

const Transactions = component('../src/pages/Transactions.jsx')
const CsvDownload = component('../src/components/CsvDownload.jsx')
const rows = [
  { id: 1, account_id: 1, kind: 'expense', date: '2026-11-15', amount: '12.50', category: 'food', currency: 'EUR', note: 'Lunch with team' },
  { id: 2, account_id: 1, kind: 'expense', date: '2026-11-16', amount: '20.00', category: 'food', currency: 'EUR', note: 'Dinner' },
]

for (const format of ['csv', 'json']) {
  test(`${format} download from Transactions uses current filters after debounce completes`, async () => {
    let exported = null
    globalThis.fetch = async (url, options) => {
      if (url === '/api/accounts') return Response.json([{ id: 1, name: 'Bank', type: 'bank', opening_balance: '100.00', balance: '67.50', currency: 'EUR', transaction_count: 2 }])
      if (url === '/api/recurring') return Response.json([])
      if (url.startsWith('/api/transactions?')) {
        const query = new URL(url, 'http://localhost').searchParams.get('q')
        return Response.json(query ? rows.filter((row) => row.note.toLowerCase().includes(query.toLowerCase())) : rows)
      }
      if (url === `/api/exports/${format}`) {
        exported = JSON.parse(options.body)
        return new Response(format === 'json' ? JSON.stringify(exported.rows) : 'id,note\r\n1,Lunch with team', {
          headers: { 'Content-Type': format === 'json' ? 'application/json' : 'text/csv' },
        })
      }
      assert.fail(`Unexpected request: ${url}`)
    }
    render(React.createElement(Transactions))
    const download = await screen.findByRole('button', { name: 'Download transactions CSV' })
    await waitFor(() => assert.equal(download.disabled, false))
    fireEvent.change(screen.getByLabelText('Search notes'), { target: { value: 'lunch' } })
    assert.equal(download.disabled, true)
    await waitFor(() => assert.equal(download.disabled, false))
    fireEvent.change(screen.getByLabelText('Export format'), { target: { value: format } })
    fireEvent.click(screen.getByRole('button', { name: `Download transactions ${format.toUpperCase()}` }))
    await screen.findByText(/Download started/)
    assert.deepEqual(exported.rows.map((row) => row.id), ['1'])
    assert.equal(exported.filters.note, 'lunch')
    assert.equal(exported.filename, `transactions.${format}`)
  })
}

test('download displays backend validation errors and permits retry', async () => {
  let calls = 0
  globalThis.fetch = async () => {
    calls += 1
    return calls === 1
      ? Response.json({ code: 'invalid_request', message: 'Export columns must be unique.' }, { status: 422 })
      : new Response('id\r\n', { headers: { 'Content-Type': 'text/csv' } })
  }
  render(React.createElement(CsvDownload, { defaultFilename: 'report.csv', buildExport: () => ({ columns: ['id'], rows: [], filters: {} }) }))
  fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
  await screen.findByRole('alert')
  assert.match(screen.getByRole('alert').textContent, /Export columns must be unique/)
  fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
  await screen.findByText(/Download started/)
  assert.equal(calls, 2)
})

test('download rejects an incorrect content type instead of saving an HTML page', async () => {
  globalThis.fetch = async () => new Response('<html>fallback</html>', { headers: { 'Content-Type': 'text/html' } })
  render(React.createElement(CsvDownload, { defaultFilename: 'report.csv', buildExport: () => ({ columns: ['id'], rows: [], filters: {} }) }))
  fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
  await screen.findByRole('alert')
  assert.match(screen.getByRole('alert').textContent, /unexpected response/)
  assert.equal(screen.queryByText(/Download started/), null)
})
