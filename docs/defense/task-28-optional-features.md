# Task #28: optional features

## Scope decision

Erti selected all three optional features in the project conversation on
15 November 2026: undo/redo, bank CSV import and matplotlib PNG charts.
Implement them as separate modules with their own tests, followed by optional
React controls outside the core workflow. The selection is recorded here as
Erti's instruction; it does not claim that a team milestone meeting occurred.

## Part 1: Command pattern

`pft/services/commands.py` adds AddCommand, DeleteCommand and TransferCommand,
each implementing execute() and undo(). History has separate undo and redo
stacks. A new successful command discards redo; failures do not move the stacks.
The module uses the existing Ledger API without changing domain/service logic.

Commands own copies of transaction data so callers cannot mutate their snapshots.
Undo and redo preserve transaction IDs and shared transfer IDs. Deleting either
transfer leg captures both rows; undo validates both target accounts and IDs
before restoring. Undo refuses to remove records that changed outside history.
Redo of a transfer checks the current source balance again.

History is session-local and not yet connected to API/React. It is not persisted
across restarts. Future integration must commit history only when repository
saving succeeds and must invalidate history after mutations outside the optional
workflow. Budget warning behavior remains the responsibility of BudgetMonitor;
this part does not change the previously reviewed warning behavior.

Tests cover balances, identity, linked-pair deletion/restoration, stack ordering,
redo clearing, empty history, failed operations, external edits, missing accounts,
mutable input isolation and monotonic allocation of new IDs after undo.

## Remaining parts

- Bank CSV parsing/import with valid rows and numbered validation errors.
- Category pie and monthly trend PNG generation using matplotlib.
- Optional API/React integration, feature gates and UI acceptance checks.
