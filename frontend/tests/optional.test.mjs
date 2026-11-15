import assert from 'node:assert/strict'
import test from 'node:test'
import { confirmImport, csvFileError, historyAction, importCanConfirm, optionalEnabled, previewImport, requestChart } from '../src/api/optional.js'

test('only explicit approved capabilities enable optional tools', () => {
  assert.equal(optionalEnabled(null), false)
  assert.equal(optionalEnabled({ undo: false, import: false, charts: false }), false)
  assert.equal(optionalEnabled({ charts: true }), true)
  assert.equal(optionalEnabled({ undo: 'false', unknown: true }), false)
})

test('CSV confirmation requires matching preview text and account', () => {
  const preview = { revision: 'snapshot', accountId: '1', csvText: 'csv', accepted: [{}] }
  assert.equal(importCanConfirm(preview, 1, 'csv'), true)
  assert.equal(importCanConfirm(preview, 2, 'csv'), false)
  assert.equal(importCanConfirm(preview, 1, 'changed'), false)
  assert.equal(importCanConfirm({ ...preview, accepted: [] }, 1, 'csv'), false)
  assert.throws(() => confirmImport(null, 1, 'csv'), /Preview/)
})

test('file validation rejects unsupported formats and oversized files', () => {
  assert.equal(csvFileError({ name: 'bank.CSV', size: 500 }), null)
  assert.ok(csvFileError({ name: 'bank.xlsx', size: 500 }))
  assert.ok(csvFileError({ name: 'bank.csv', size: 1_000_001 }))
})

test('preview, confirmation and history preserve their backend contracts', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push([url, JSON.parse(options.body)])
    return Response.json({ revision: 'r1', accepted: [{}] })
  }
  try {
    await previewImport('2', 'raw CSV')
    await confirmImport({ revision: 'r1', accepted: [{}], accountId: '2', csvText: 'raw CSV' }, '2', 'raw CSV')
    await historyAction('safe token', { action: 'undo' })
    assert.deepEqual(calls, [
      ['/api/optional/import/preview', { account_id: 2, csv_text: 'raw CSV' }],
      ['/api/optional/import/confirm', { account_id: 2, csv_text: 'raw CSV', expected_revision: 'r1' }],
      ['/api/optional/history/safe%20token', { action: 'undo' }],
    ])
  } finally { globalThis.fetch = original }
})

test('PNG requests use selected filters and require a PNG response', async () => {
  for (const kind of ['categories', 'trend']) {
    const blob = await requestChart(kind, { start: '2026-11-01', end: '2026-11-15', months: 6 }, {
      fetchImpl: async (url) => {
        assert.ok(url.startsWith(`/api/optional/charts/${kind}?`))
        assert.ok(url.includes('end=2026-11-15'))
        return new Response('PNG bytes', { headers: { 'Content-Type': 'image/png' } })
      },
    })
    assert.equal(await blob.text(), 'PNG bytes')
  }
  await assert.rejects(requestChart('unknown', {}), /Unsupported/)
  await assert.rejects(requestChart('trend', {}, { fetchImpl: async () => new Response('html') }), /PNG/)
  await assert.rejects(requestChart('trend', {}, {
    fetchImpl: async () => Response.json({ detail: 'Install charts extra' }, { status: 503 }),
  }), /Install charts extra/)
})
