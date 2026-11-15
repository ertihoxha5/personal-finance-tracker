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

## Part 2: monthly report exports and React acceptance checks

Monthly reports accept a positional month, retaining the previous --month option.
Conflicting months give a friendly error. Without --export, the existing console
summary is unchanged. With --export, the CLI writes the report and prints its path:

```powershell
.venv\Scripts\python.exe -m pft report monthly 2026-11 --export csv
.venv\Scripts\python.exe -m pft report monthly --month 2026-11 --export json --out summary.json
.venv\Scripts\python.exe -m pft report monthly 2026-11 --export md --out summary.md
```

The default path is monthly-report-MONTH.FORMAT in the current directory. --out
requires --export. Both export commands use the same registry-based file helper;
no concrete format names or format branches are added to the CLI. File/path errors
are friendly failures with exit code 1. Existing files follow each strategy's
atomic replacement behavior.

Monthly report rows have month, section, label, value and unit columns. They
contain income, expenses, net and savings rate, followed by spending categories.
Money stays typed until exporter formatting, so a negative numeric net is not
mistaken for user-entered formula text. JSON values retain exact decimal text.
An empty month contains four zero-valued summary rows.

The React download integration already uses the approved CSV/JSON/Markdown
endpoints from #24. Added component interaction tests mount the actual
Transactions page, change Search notes, verify download is disabled during the
debounce gap, and assert CSV/JSON requests contain only matching rows with the
current filters and correct filename. Additional tests cover backend validation
messages, retry and rejection of an HTML response. The API client now displays
the standard {message} error shape as well as endpoint {detail} messages.

These are automated jsdom/React Testing Library interaction tests with mocked
HTTP, not a live browser walkthrough. Existing API integration tests verify the
actual response content types and CSV formula neutralization.

Both implementation parts are complete. No repository writes or changes to
teammates' financial calculations were required.
