# Task #32: CLI export commands

## Part 1: transaction exports

The additive `export transactions` subcommand takes required `--format` and
`--out` arguments. It loads stored transactions, passes their existing to_row()
representation to the selected strategy, writes the file and prints its absolute
path. No repository save occurs. Existing account, list and report behavior is
unchanged.

```powershell
.venv\Scripts\python.exe -m pft export transactions --format csv --out transactions.csv
.venv\Scripts\python.exe -m pft export transactions --format json --out transactions.json
.venv\Scripts\python.exe -m pft export transactions --format md --out transactions.md
```

The CLI imports only Exporter. Selection goes through Exporter.for_format(), not
concrete strategies or format-specific conditionals. Unknown formats become a
friendly InvalidChoiceError with the registry's current list. File-system write
errors become StorageError; main() prints them and returns exit code 1.

Tests cover all three formats, JSON loading and text amounts, Markdown structure,
unknown formats, a dynamically registered additional strategy, write failures,
empty output and the absence of repository writes. This demonstrates loose
coupling: an extra registered strategy needs no CLI modification.

## Remaining part

- Monthly report export with positional month, retaining the existing --month
  option, with registry-based format selection.
- Verify the existing React CSV/JSON download controls with active filters,
  content types and failure messages as required by the React deliverable.
