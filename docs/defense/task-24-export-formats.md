# Task #24: JSON, Markdown and safe CSV downloads

## Design and requirements

JsonExporter and MarkdownExporter extend Exporter and register themselves with
`fmt="json"` and `fmt="md"`. The original Exporter and CsvExporter classes are
unchanged. This demonstrates Strategy and the Open/Closed principle: callers
select an implementation through `Exporter.for_format`.

JSON is an array of row objects, indented by two spaces. Money is serialized as
exact decimal text, dates as ISO text and enum members as their names. Ordinary
JSON integers and null remain integers and null. Markdown writes a header,
separator and data rows; pipes, HTML and newlines are escaped for table cells.
Both exporters replace the destination only after serialization succeeds.

The CSV guard is an additional string registration on the existing
`format_value` singledispatch function. Strings beginning with =, +, - or @ gain
one leading apostrophe. Already guarded strings are unchanged. Typed Money and
numbers keep their numeric representation; negative strings receive the guard.
The guard is specific to CSV: JSON and Markdown preserve literal formula text.

## Downloads

The existing CSV endpoint remains available. JSON and Markdown use
`POST /api/exports/json` and `POST /api/exports/md` with the same snapshot fields:
filename, columns, rows and filters. Paths, mismatched extensions, duplicate
columns and unknown row fields are rejected. Only csv/json/md are approved.

Transactions and Dashboard share the format picker. Selecting a format updates
the filename extension, endpoint, response type and download label. Transactions
captures the filters with the response and disables export while results are
pending, failed, invalid or from a different query, including the debounce gap.
The server serializes the supplied snapshot, rather than independently querying
the repository. Dashboard exports the selected monthly summary and categories;
its separate custom category date range does not change that monthly report.

## Manual verification

1. Run the backend and frontend using the project's existing startup commands.
2. In Transactions search for lunch and choose descending amount order.
3. Download CSV, JSON and Markdown; confirm matching records and order.
4. Change a filter and immediately try downloading: wait for matching results.
5. Export a synthetic note `=SUM(A1)` as CSV and inspect the raw CSV: it should
   contain `'=SUM(A1)`. JSON and Markdown should keep the literal note.
6. In Dashboard select a month and download all three formats. Open JSON with
   json.load and view Markdown in a Markdown preview.

Automated coverage includes backend formula neutralization, format and filename
validation, JSON loading/indentation, Markdown table escaping, empty results,
failed sources, request contracts and stale-result export gating. A fresh browser
walkthrough remains a manual verification step.
