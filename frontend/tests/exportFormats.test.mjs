import assert from 'node:assert/strict'
import test from 'node:test'
import { EXPORT_FORMATS, exportSnapshotReady, filenameError, requestExport, transactionExport } from '../src/api/exports.js'

test('only approved formats are offered and filenames must match', () => {
  assert.deepEqual(Object.keys(EXPORT_FORMATS), ['csv', 'json', 'md'])
  for (const format of Object.keys(EXPORT_FORMATS)) {
    assert.equal(filenameError(`report.${format}`, format), null)
    assert.ok(filenameError(`../report.${format}`, format))
  }
  assert.ok(filenameError('report.md', 'json'))
})

for (const [format, mime] of [['json', 'application/json'], ['md', 'text/markdown']]) {
  test(`${format} downloads post the selected snapshot and validate the response type`, async () => {
    const payload = { filename: `report.${format}`, columns: ['amount'], rows: [{ amount: '12.50' }] }
    const blob = await requestExport(payload, format, {
      fetchImpl: async (url, options) => {
        assert.equal(url, `/api/exports/${format}`)
        assert.deepEqual(JSON.parse(options.body), payload)
        return new Response('export', { headers: { 'Content-Type': mime } })
      },
    })
    assert.equal(await blob.text(), 'export')
    await assert.rejects(requestExport(payload, format, {
      fetchImpl: async () => new Response('wrong', { headers: { 'Content-Type': 'text/html' } }),
    }), /unexpected response/)
  })
}

test('unsupported formats never send a request', async () => {
  await assert.rejects(requestExport({ filename: 'report.xml' }, 'xml', {
    fetchImpl: () => assert.fail('must not fetch'),
  }), /Unsupported export format/)
})

test('exports wait for successful results matching active filters, including debounce and retry', () => {
  const data = { query: 'q=lunch', filters: { note: 'lunch' }, rows: [] }
  assert.equal(exportSnapshotReady({ status: 'success', data }, 'q=lunch'), true)
  assert.equal(exportSnapshotReady({ status: 'success', data }, 'q=dinner'), false)
  for (const status of ['loading', 'error']) {
    assert.equal(exportSnapshotReady({ status, data }, 'q=lunch'), false)
  }
  assert.equal(exportSnapshotReady({ status: 'success', data }, 'q=lunch', true), false)
  const exported = transactionExport(data.rows, data.filters)
  data.filters.note = 'dinner'
  assert.equal(exported.filters.note, 'lunch')
})
