# Task #11 – Ledger, events and Observer: defense notes

## What the Ledger is
- Holds every `Account` in a private dict (composition: accounts live and die with the Ledger).
- `net_worth` is a property: the sum of all account balances, zero for an empty ledger.
- `all_transactions()` uses `itertools.chain.from_iterable`, so it walks every account lazily
  without building a list.
- Account IDs are assigned by the Ledger and never reused, even after `close_account`.

## Observer pattern with `typing.Protocol`
- `Observer` only needs `update(event)`. Any object with that method works; no base class.
  The Ledger does not know who listens (a budget monitor in #27, a test recorder now).
- Events are frozen dataclasses (`TransactionAdded`, `TransactionRemoved`): immutable, so an
  observer cannot change what the next observer sees.
- `subscribe` ignores repeats (one event per observer per change). `_notify` loops over a copy
  so an observer may unsubscribe itself while being notified.

## Decision: what happens when an observer raises (review of 12 Nov 2026)
- Observers are told *after* the change is made, so the change is final. An observer error must
  not make `add_transaction` / `remove_transaction` look as if it failed.
- `_notify` catches `Exception` per observer, logs it with the traceback (`logging`, no print),
  and carries on. The mutation stands, the caller sees no exception, and every other observer
  still gets the event, whether it was subscribed before or after the failing one.
- Not caught: `BaseException` (`KeyboardInterrupt`, `SystemExit`) must still stop the program.
- Trade-off: a broken observer is only visible in the log. If #27 needs failures surfaced (for
  example a budget alert that must not be lost), it should report its own errors.
- Tests: `test_failing_observer_does_not_undo_or_hide_the_change` and
  `test_failing_observer_does_not_break_remove_either`.

## React deliverable: status
- Done: per-account balance and the net-worth card on Accounts and Dashboard, refreshed after
  every successful mutation. Money is shown exactly as received; React does no arithmetic.
- **Deferred, depends on #18 and #14:** these values come from `frontend/src/api/accounts.js`
  (in-memory fixtures), not from FastAPI/Ledger responses. The API has only `/api/health`;
  nothing loads the Ledger from SQLite or saves it yet. Planned routes: `GET /api/accounts`,
  `GET /api/net-worth`, plus the create/rename/delete/edit mutations, wired in #36. The
  function signatures in `accounts.js` are kept so only the bodies change.
- So the full React deliverable of #11 is **not** complete until that integration lands.
