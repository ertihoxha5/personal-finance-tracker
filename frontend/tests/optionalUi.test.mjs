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
afterEach(() => { cleanup(); globalThis.fetch = originalFetch })
after(() => dom.window.close())

// Compile the actual components with the project's esbuild, without creating test artifacts.
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

const OptionalTools = component('../src/pages/OptionalTools.jsx')
const ImportTools = component('../src/components/optional/ImportTools.jsx')
const HistoryTools = component('../src/components/optional/HistoryTools.jsx')
const ChartTools = component('../src/components/optional/ChartTools.jsx')
const accounts = [{ id: 1, name: 'Bank' }, { id: 2, name: 'Savings' }]
const CSV = 'date,amount,category\n2026-11-15,-12.50,food'

test('disabled features hide all mutation and download controls', async () => {
  globalThis.fetch = async () => Response.json({ undo: false, import: false, charts: false })
  render(React.createElement(OptionalTools))
  await screen.findByText(/Optional tools are disabled/)
  assert.equal(screen.queryByRole('button', { name: 'Preview CSV' }), null)
  assert.equal(screen.queryByRole('button', { name: 'Start new history' }), null)
  assert.equal(screen.queryByRole('button', { name: 'Download trend PNG' }), null)
})

test('each tool is shown only when its capability is enabled', async () => {
  globalThis.fetch = async (url) => Response.json(url.endsWith('/features')
    ? { undo: false, import: false, charts: true } : [])
  render(React.createElement(OptionalTools))
  await screen.findByRole('button', { name: 'Download trend PNG' })
  assert.equal(screen.queryByRole('button', { name: 'Preview CSV' }), null)
  assert.equal(screen.queryByRole('button', { name: 'Start new history' }), null)
})

test('CSV preview renders row errors, gates confirmation and clears after a successful import', async () => {
  const calls = []
  let changes = 0
  globalThis.fetch = async (url, options) => {
    calls.push([url, JSON.parse(options.body)])
    return Response.json(url.endsWith('/preview') ? {
      revision: 'r1', accepted: [{ row_number: 2, transaction: { date: '2026-11-15', kind: 'expense', amount: '12.50', currency: 'EUR', note: 'Lunch' } }],
      errors: [{ row_number: 3, reason: 'Invalid date' }],
    } : { accepted: [{}], errors: [{}], warnings: [] })
  }
  render(React.createElement(ImportTools, { accounts, onChanged: () => { changes += 1 } }))
  const confirm = screen.getByRole('button', { name: 'Confirm valid rows' })
  assert.equal(confirm.disabled, true)
  fireEvent.change(screen.getByLabelText('Import into account'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('CSV contents'), { target: { value: CSV } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }))
  await screen.findByText('Invalid date')
  assert.equal(confirm.disabled, false)
  fireEvent.click(confirm)
  await screen.findByText(/Imported 1 transaction/)
  assert.equal(confirm.disabled, true)
  assert.equal(changes, 1)
  assert.equal(calls[1][1].expected_revision, 'r1')
})

test('editing previewed text requires another preview before confirmation', async () => {
  globalThis.fetch = async () => Response.json({ revision: 'r1', accepted: [{ row_number: 2, transaction: {} }], errors: [] })
  render(React.createElement(ImportTools, { accounts, onChanged: () => {} }))
  fireEvent.change(screen.getByLabelText('Import into account'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('CSV contents'), { target: { value: CSV } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }))
  const confirm = screen.getByRole('button', { name: 'Confirm valid rows' })
  await waitFor(() => assert.equal(confirm.disabled, false))
  fireEvent.change(screen.getByLabelText('CSV contents'), { target: { value: CSV + '\n' } })
  assert.equal(confirm.disabled, true)
})

test('history buttons follow server capabilities and outside changes clear their state', async () => {
  let reads = 0
  globalThis.fetch = async (url, options) => {
    if (url.includes('/transactions')) return Response.json([])
    if (options?.method === 'POST') return Response.json({ token: 'session1', can_undo: true, can_redo: false })
    reads += 1
    return Response.json({ token: 'session1', can_undo: false, can_redo: false, reset: true })
  }
  render(React.createElement(HistoryTools, { accounts, onChanged: () => {} }))
  fireEvent.click(screen.getByRole('button', { name: 'Start new history' }))
  const undo = await screen.findByRole('button', { name: 'Undo' })
  await waitFor(() => assert.equal(undo.disabled, false))
  assert.equal(screen.getByRole('button', { name: 'Redo' }).disabled, true)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh history' }))
  await screen.findByText(/History was cleared/)
  assert.equal(undo.disabled, true)
  assert.equal(reads, 1)
})

test('failed import confirmation leaves a visible error and does not report saved data', async () => {
  let changes = 0
  globalThis.fetch = async (url) => url.endsWith('/preview')
    ? Response.json({ revision: 'r1', accepted: [{ row_number: 2, transaction: {} }], errors: [] })
    : Response.json({ code: 'command_error', message: 'Preview the CSV again.' }, { status: 422 })
  render(React.createElement(ImportTools, { accounts, onChanged: () => { changes += 1 } }))
  fireEvent.change(screen.getByLabelText('Import into account'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('CSV contents'), { target: { value: CSV } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }))
  const confirm = screen.getByRole('button', { name: 'Confirm valid rows' })
  await waitFor(() => assert.equal(confirm.disabled, false))
  fireEvent.click(confirm)
  await screen.findByRole('alert')
  assert.match(screen.getByRole('alert').textContent, /Preview the CSV again/)
  assert.equal(changes, 0)
  assert.equal(screen.queryByText(/Imported 1 transaction/), null)
})

test('PNG control downloads with the selected month and number of months', async () => {
  let downloaded = ''
  let requested = ''
  const originalClick = dom.window.HTMLAnchorElement.prototype.click
  dom.window.HTMLAnchorElement.prototype.click = function () { downloaded = this.download }
  globalThis.fetch = async (url) => {
    requested = url
    return new Response('png', { headers: { 'Content-Type': 'image/png' } })
  }
  try {
    render(React.createElement(ChartTools))
    fireEvent.change(screen.getByLabelText('Ending month'), { target: { value: '2026-10' } })
    fireEvent.change(screen.getByLabelText('Number of months'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Download trend PNG' }))
    await screen.findByText(/Download started/)
    assert.equal(requested, '/api/optional/charts/trend?end=2026-10&months=3')
    assert.equal(downloaded, 'trend-2026-10-3-months.png')
  } finally { dom.window.HTMLAnchorElement.prototype.click = originalClick }
})
