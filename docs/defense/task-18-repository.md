# Task #18 – Repository and atomic save: defense notes

## Repository pattern
- `Repository` (abstract) has two methods: `load() -> Ledger` and `save(ledger)`. The rest of
  the program never knows where data lives. Three implementations sit behind it:
  `CsvRepository` (folder of four CSV files), `JsonRepository` (one file) and
  `SqliteRepository` (the one the API uses).
- The same parametrized tests run against all three (`tests/integration/test_repository.py`),
  which is the proof that they are interchangeable.
- A missing `data/` folder, file or database gives an empty Ledger, not an error.

## Atomic save: `atomic_write(path)` (context manager)
- Write to `out.csv.tmp`, flush and `fsync`, then `os.replace(tmp, path)`. `os.replace` is atomic,
  so a reader sees the old file or the new one, never a half-written mix.
- `finally` deletes the temporary file after any failure. Tests simulate a crash while writing and
  a failing `os.replace`; in both the old file is unchanged.
- Limit: CSV writes several files in a row, so each file is atomic but the set is not. That is why
  the API uses SQLite, where one database transaction covers everything.

## SQLite
- One transaction per save: delete all rows, insert the Ledger's rows, commit. Any error rolls the
  whole save back (tested with a duplicate account name that breaks the UNIQUE constraint halfway).
- Amounts are integer cents, always positive; `kind` (and a transfer's `direction`) gives the sign.
  A value with more than two decimals is refused, never rounded.
- `db.init_db` upgrades a task-#5 database (signed amounts, `description`) in one transaction,
  keeping every row. Tested with a hand-built old database.
- Connections are opened per operation and closed after it.

## API (FastAPI) and the lock
- `LedgerStore.write` = lock, load from SQLite, change the Ledger, save, answer. The response is
  sent only after the commit, so "saved" in React is true. The lock stops two requests from
  overwriting each other's change.
- Domain errors become `{code, message, field}` with status 404 (not found), 409 (duplicate),
  422 (invalid) or 500 (`storage_error`). A rejected change is never saved.
- Routes: `GET /api/accounts`, `GET /api/net-worth`, `POST /api/accounts`,
  `PATCH /api/accounts/{id}`, `DELETE /api/accounts/{id}`, `GET /api/accounts/{id}/transactions`,
  `POST /api/transactions`, `PUT` and `DELETE /api/accounts/{id}/transactions/{tx_id}`.

## React deliverable
- `frontend/src/api/accounts.js` now calls the API instead of browser-memory fixtures. This also
  closes the #11 deferral: balances and net worth come from the Ledger.
- `SaveStatus` shows Saving…, All changes saved, or Not saved plus the server message.
- Checked by hand in the browser with a seeded database: add account, delete transaction, stop the
  backend (Not saved shown, nothing changed), restart it, and the data and balances were unchanged.

## Known limits (not done in this task)
- Budgets and recurring rules do not exist yet (#25, #27). Their CSV files are header-only and
  never overwritten; JSON keeps whatever is already stored under `budgets` and `recurring`.
- Account "created date" from Appendix B is not stored: `Account` has no such field.
- Transfers cannot be created or edited through the API (needs `Ledger.transfer`, #26). Deleting
  an account that holds one side of a transfer leaves the other side without its pair.
- The React Transactions page and Dashboard charts still use fixtures; only Accounts and the
  net-worth cards use the API. Adding a transaction from the UI is not built; the route exists.
- Whole-ledger save on every change is simple and fine for this data size; it would not scale.
