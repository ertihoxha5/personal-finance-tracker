# Task #17 – TransactionFactory: defense notes

## Factory pattern: the caller never names the class
- `pft/domain/factory.py` is the one place that turns text into a `Transaction`.
  `TransactionFactory.from_input(...)` reads what a user typed; `TransactionFactory.from_row(row)`
  reads a stored CSV row. Both return `Transaction`; the caller does not know or care whether it
  got `Income`, `Expense` or `Transfer`.
- Why it helps: parsing rules (decimal comma, strict ISO date, which error to raise) live in one
  place. The CLI, the API (#19) and the repository (#18) all get the same behaviour, and adding a
  kind touches one file instead of every caller.
- It is a "simple factory" made of class methods, not the GoF Factory Method (no subclass
  overrides a creation method). The class is never instantiated.

## Dictionary dispatch instead of if/elif
```python
_CLASSES: ClassVar[dict[Kind, type[Transaction]]] = {
    Kind.INCOME: Income, Kind.EXPENSE: Expense, Kind.TRANSFER: Transfer,
}
return cls._CLASSES[kind](id=..., account_id=..., amount=..., ...)
```
- Classes are objects in Python, so a dict can map a `Kind` to the class that builds it.
  A lookup replaces an `if kind == ... elif ...` chain; it is one line no matter how many kinds.
- Adding a kind = one dict entry. `test_registry_covers_every_kind` asserts the keys equal
  `set(Kind)`, so a new `Kind` member without a class fails the tests instead of failing at runtime.
- **Transfer needs two more fields.** A plain dict of classes is not enough because `Transfer`
  also takes `direction` and `transfer_id`. A second mapping, `_ROW_EXTRAS`, gives each kind a small
  function that returns its extra keyword arguments: `{}` for income/expense (after checking the
  transfer columns are empty), `{direction, transfer_id}` for transfers. Still no if/elif on kind.
- The React side uses the same idea: `TRANSACTION_TYPES` in `frontend/src/api/transactions.js` maps
  `"kind/direction"` to the form value, label and sign.

## How this differs from `Money.of` and `Category.from_text`
- Those are **alternative constructors**: a class method on a class that returns *that same class*
  (`Money.of` → `Money`, `Category.from_text` → `Category`).
- The factory returns *one of several subclasses* chosen at runtime. That choice is what makes it
  a factory. It uses the alternative constructors as building blocks (`Kind.from_text`,
  `Category.from_text`, `Money.of`).

## Round trip: `from_row(t.to_row()) == t`
- `to_row()` (#14) writes every column in `CSV_COLUMNS` as text; `from_row` reads them back.
- The stored `id` is restored, never generated. Equality compares every field including `id`,
  so a new id would break the round trip and the repository would duplicate rows.
- Currency is restored from its column, so a USD expense stays USD.
- Parametrized test over Income, Expense, Transfer OUT and Transfer IN.

## Decisions taken (the checklist's open points)
| Question | Decision | Why |
|---|---|---|
| Transfers through `from_input` | Rejected with `InvalidTransferError` pointing to `Ledger.transfer` | `from_input` has no direction or transfer_id, and a transfer is always a linked OUT/IN pair |
| Where `12,50` is accepted | User text only. Rows must be `12.50` | Rows are machine-written by `to_row`; accepting commas there would hide corrupt files |
| Ambiguous amounts | `1.234,50`, `1,234.50`, two commas, more than 2 decimals rejected | `1,234` could mean 1.234 or 1234; same rule as React's `parseMoneyInput` |
| Dates | Exactly `YYYY-MM-DD` (regex, then `date.fromisoformat`) | Since 3.11 `fromisoformat` also takes `20261117` and `2026-W47-2`; one stored format |
| Bad rows | Amount → `InvalidAmountError`, date → `InvalidDateError`, category → `InvalidCategoryError`; missing column, unknown kind/direction, non-integer id, transfer columns on income/expense → `DataImportError` | Value errors keep their specific code; structure errors share one type the repository can catch and add the row number to |
| IDs in `from_input` | Required keyword `transaction_id` | `transaction.py` says the caller (Ledger/repository) assigns IDs; the factory never invents one |
| Empty date in `from_input` | Rejected (`InvalidDateError`) | No hidden clock in the domain; the CLI/form can default to today before calling |

## Edge cases worth knowing
- `csv.DictReader` fills a short line with `None`. `from_row` treats `None` as a missing column
  (`DataImportError`), which is why the row type is `Mapping[str, str | None]`.
- Zero and negative amounts reach `Money.of` fine, then the #12 `PositiveAmount` descriptor
  on the transaction raises `InvalidAmountError`. The factory does not repeat that rule.
- Unknown kind or category messages list every valid value (from `_parse` in #10).

## React deliverable: shared API adapter
- `frontend/src/api/transactions.js`: `fromApi(dto)` and `toApi(formValues)` are the only
  places the DTO is mapped. `account_id` → `accountId`, `transfer_id` → `transferId`
  (`API_TO_FORM_FIELD`, also used to rename server error fields in the form).
- `transactionType(kind, direction)` looks up label, sign, tone and form value. An unknown pair
  (new kind, transfer without direction, income with one) returns "Unknown type" with the raw
  value and a readable message instead of throwing; `TransactionRows` shows the message above
  the table and the row with an unsigned amount.
- `toDto`, `kindDisplay` and `signedAmount` were removed from `lib/transactions.js` (one mapping only).
- Demo: `/dev/transactions` (dev only) with fixtures for all three kinds, both directions and one
  unknown kind (`refund`). The live API is wired in #19.

## Evidence
- `tests/unit/test_factory.py`: 49 tests, 100% line coverage of `pft/domain/factory.py`.
- `frontend/tests/transactionsApi.test.mjs`: lookup completeness against the Python enums,
  unknown types, `fromApi`/`toApi`, field names vs `CSV_COLUMNS`.
