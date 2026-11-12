# Task #16: exporter strategies and CSV downloads

## Python design

`pft/infrastructure/exporters.py` defines the abstract Exporter interface.
Subclasses register themselves through `__init_subclass__(fmt=...)`.
`Exporter.for_format("csv")` returns a CsvExporter. Unknown formats raise
ValueError with the known format names. Format lookup ignores surrounding
whitespace and case. Duplicate registrations are rejected.

`format_value` uses `functools.singledispatch` to choose formatting by runtime
type. Money becomes exact decimal text such as `12.50`, dates become ISO text,
and Enum members become their names. Existing transaction `to_row()` output
already contains serialized strings, preserving its lowercase enum values.
None becomes an empty cell.

CsvExporter uses `csv.DictWriter`, a header row, UTF-8 with a BOM, and CRLF line
endings. Quoting handles commas, double quotes and embedded newlines. Default
column order follows the first row. Explicit fieldnames support report schemas,
including empty reports. Empty transaction exports use the existing CSV_COLUMNS.

Each file is written beside its destination under a temporary name and replaced
only after every row succeeds. An invalid row or failing input generator leaves
an existing destination intact and cleans the temporary file.

## Download integration

`POST /api/exports/csv` accepts filename, columns, rows and filters. It validates
the filename and column schema, uses CsvExporter, and returns a CSV attachment.
The response includes Content-Disposition with the requested filename.
Temporary files are removed after the response body has been read. File errors
produce a recoverable message without exposing server paths.

The screens currently use synthetic data. Their adapters send a snapshot of the
visible selection to this endpoint. Filters and sorting accompany the snapshot
as metadata. The endpoint serializes the supplied rows in their supplied order.
Repository-backed selection belongs to later integration work.

- Transactions exports the filtered rows in visible sort order, using the ten
  existing transaction CSV columns. Invalid filters disable the export button.
- Dashboard exports the selected month's existing summary and category totals.
  Columns are month, section, label, value and unit. The control is disabled
  while the selected month is loading or has failed, preventing stale exports.
- The reusable CsvDownload control accepts a filename, shows pending and failed
  states, prevents concurrent requests, and allows retry after failure. Request
  cancellation on unmount prevents a download after leaving the screen.
- A success message says the download started. The browser controls where the
  file is saved.

Other formats and the CSV injection guard remain assigned to #24.

## Verification

Final automated checks passed on Python 3.12 and Node 24:

- 296 Python tests, including 19 exporter tests and 13 endpoint tests.
- 52 frontend tests, including eight export adapter/request tests.
- 100% statement coverage for the export endpoint, 97% for exporters and 99%
  overall Python coverage.
- Ruff lint and formatting, mypy, frontend lint and production build.

An additional cross-language check built a request using the real frontend
selection and export adapters, passed it to the FastAPI endpoint, and parsed
the resulting CSV. Searching groceries and sorting amount descending yielded
IDs 202, 210, 209 with amounts 64.50, 20.01, 20.00. All ten columns matched the
request schema. After restarting the older project development server, the
same request to the live HTTP endpoint on port 8000 returned status 200, the
requested attachment filename and the expected row order. The review file is
`data/task-16-review.csv`, which is ignored by Git.

Excel verification passed. Excel detected UTF-8 in its Text Import Wizard.
After selecting Comma as the delimiter, the worksheet showed the ten columns
and three rows with the expected IDs, amounts and notes. Excel may display
dates and numeric decimal places using its own cell formatting. If the wizard
appears, select Delimited, UTF-8, then Comma with double quotes as text qualifier.

The browser's Transactions screen exposes the filename and download controls.
Further browser interaction was interrupted by active user input. Verification
of clicking the control, pending/error states, keyboard interaction and narrow
layout remains pending. The older running API initially exposed only
`/api/health`. It was restarted and the live export endpoint verified. The
frontend now explains the required restart if an export request receives 404
from an older server process.
To complete the browser check:

1. Start the backend with `python -m pft serve` and frontend with `npm run dev`.
   Restart an older backend process so it loads the new export router.
2. Open `/transactions`, search groceries, select Amount descending and download
   `transactions.csv`. Check the three rows and their order against the above.
3. Change the filename and repeat. Invalid filenames should show an inline error.
4. Download a Dashboard report for two different months. Verify the month and
   existing summary/category values in each file.
5. Stop the backend, try a download, verify the failure message, restart the
   backend and retry. While pending, the filename and download button are disabled.
6. Use Tab/Enter and a narrow viewport to verify labels, focus and layout.

From the repository root, run pytest, Ruff and mypy. From `frontend`, run
`node --test tests/*.test.mjs`, `npm run lint` and `npm run build`.

For the defense, explain the Strategy pattern, subclass self-registration,
singledispatch, CSV quoting, exact money serialization and atomic file replacement.
AI assistance was used for implementation and tests using the project plan,
the existing transaction column contract and current screen data shapes.
