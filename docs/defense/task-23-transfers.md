# Task #23 – Transfers between accounts: defense notes

FR-14 (Should). Owner: Isa Bilalli. Needs #11 (Ledger) and #14 (Transfer class).

## What a transfer is
- Money that moves between two of the user's own accounts. It is **not** income or expense, so it
  changes two balances but never net worth and never the income/expense totals.
- It is stored as **two linked `Transfer` objects** (#14): direction `OUT` in the source account,
  `IN` in the destination, both with the same `transfer_id`. `Transfer.signed_amount()` gives the
  sign from the direction, so `Account.balance` needs no special case.

## `Ledger.transfer(src, dst, money, date, note)` (`pft/services/ledger.py`)
1. Rejects `src == dst` with `InvalidTransferError` (`field="to_account_id"`).
2. Looks up both accounts first (`AccountNotFoundError` before anything changes).
3. Builds both `Transfer` rows **before** touching any account, so the #12 descriptors check the
   amount (`PositiveAmount`), date and note up front. One fresh `uuid4` is the `transfer_id`.
4. Rejects a transfer that would take the source below zero (`InvalidTransferError`,
   `field="amount"`). Moving the whole balance down to exactly 0.00 is allowed.
5. **All or nothing**: adds the OUT side, then the IN side. If the second `add` fails (for example a
   currency mismatch), the first is removed again and the error is re-raised. No half transfer.
6. Observers (#11) are told only after both sides are in, one `TransactionAdded` per side.
7. Returns `(out_side, in_side)`.

Transaction IDs come from Florent's `next_transaction_id()` (#18): one more than the highest ID
in the ledger, so the two rows never clash with existing IDs.

## Deleting one side deletes both
`remove_transaction` now checks whether the removed item is a `Transfer`; if so it finds the other
row with the same `transfer_id` (`_counterpart`) and removes it too, then sends both
`TransactionRemoved` events. The return value is unchanged (the row that was asked for), so
existing callers keep working. An orphan side (partner already gone) is removed alone.

## Reports ignore transfers
#19 (`pft/services/reports.py`, `pft/api/dashboard.py`) already leaves transfers out **by kind**
(`Kind.TRANSFER`), not by category. `test_transfers_stay_out_of_dashboard_income_and_expense`
checks that the month's income/expense summary is identical before and after a transfer.
#26 CategoryReport should follow the same rule. Net worth includes both sides and stays the same.

## API: `POST /api/transfers` (`pft/api/accounts.py`)
- Body: `{from_account_id, to_account_id, amount, date, note}`; amount is a decimal string, date ISO.
- Runs `Ledger.transfer` inside `LedgerStore.write`, so the change is saved only when both sides
  were added; an error skips the save. Returns `201` with both sides `[out, in]` as transaction
  DTOs (same shape as every other transaction route).
- Errors use the `{code, message, field}` shape: `invalid_transfer` (422, field `to_account_id` or
  `amount`), `invalid_amount` / `invalid_date` (422), `account_not_found` (404).
- The existing `DELETE /api/accounts/{id}/transactions/{tx_id}` calls `remove_transaction`, so
  deleting either side removes both.

## All-or-nothing: why not a transaction or a lock?
- The ledger is in memory and single-threaded, so "compensate on failure" (undo the first add) is
  enough. The repository (#18) gives the same guarantee on disk with its atomic save.
- The checks run before the first change, so in practice only an unexpected error (currency
  mismatch) reaches the rollback. A test forces that case with a USD account.

## React (Accounts screen)
- `TransferForm.jsx`: From / To selects, Amount (`MoneyInput`), Date, optional Note.
  `lib/transfers.js#validateTransfer` blocks an empty field, a non-positive amount and the same
  account on both sides before sending. Server errors appear under the field they name.
- `api/accounts.js#createTransfer` posts to `/api/transfers` through the shared `request()` helper
  and maps both sides with `toTransaction`. The form renames the server's `to_account_id` field to
  `toAccountId` so the message shows under the right select.
- After success the page's `mutate()` reloads the accounts list and net worth, so **both balances
  refresh** and the success notice names both accounts.
- Income/expense totals: they are calculated on the server, which skips `Kind.TRANSFER`.
  React never adds anything up.

## Tests
- `tests/unit/test_transfer.py` (13 cases): the plan's example (Bank 100 / Cash 40 → 60 / 80, net
  worth unchanged), linked sides, separate IDs, same-account rejected, above-balance rejected,
  exact-balance allowed, zero/negative amount, unknown account, rollback, linked delete, observer
  events, orphan delete.
- `tests/integration/test_transfers_api.py` (9 cases): the route on a real SQLite file, error
  shapes, dashboard totals unchanged, linked delete.
- `frontend/tests/transfers.test.mjs` (5 cases): form validation, request body and error mapping
  with a mocked `fetch`.

## Coordination with Florent (owner of `ledger.py`) – draft, not sent
> Hi Florent, for #23 I added `Ledger.transfer(src, dst, money, date, note)` and changed
> `remove_transaction` so deleting one transfer side removes both (it still returns the row you
> asked for). It uses your `next_transaction_id()` and one private helper, `_counterpart`. I also
> added `POST /api/transfers` in `pft/api/accounts.py`, next to your routes. Your ledger and API
> tests still pass. For #26, please leave out `Kind.TRANSFER` rows like the dashboard does. Can
> you review the ledger and API parts before I push?

## Possible questions
- *Why two rows and not one row with two account IDs?* Each account owns its transactions and
  derives its balance from them (#11); one row per account keeps `Account.balance` a simple sum and
  matches the CSV layout (`transfer_id`, `direction` columns).
- *Why can't a transfer recur?* `Transfer.copy_for` raises: copies would share a `transfer_id`
  and link unrelated pairs (#14 / #25).
- *What if the source is a credit card with a negative balance?* The rule in the plan is "never
  below zero", so a transfer out of an already-negative account is rejected. This is a team
  decision we could revisit.
