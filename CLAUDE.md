# Personal Finance Tracker — project context

MSc Advanced Programming group project (React + Python). Presentation and defense on 8 Dec 2026.

## The task plan is the source of truth

- `docs/plan/Personal_Finance_Tracker_Task_Plan_v6.1.pdf` is the original.
- `docs/plan/task-plan-v6.1.txt` is a searchable text copy. Search it for `^#NN ` to find a task's section.
- Each task section lists: owner, due date, prerequisites, steps, "Done when" checks, deliverable files,
  "Be ready to explain" topics, the React deliverable, and sometimes an "Original interface sketch".
  Follow these sketches and the deliverable paths exactly.
- Appendix A covers requirements (FR-01..FR-23), Appendix B the folder layout and data model,
  and Appendix C the submission documentation.
- Each task also has a per-task checklist spreadsheet (e.g. "Task #10 Enums & Exceptions Checklist.xlsx")
  that breaks the plan into steps. The plan wins if the two disagree.

## Team and review

- Isa Bilalli: setup, domain, validation, budgets (#05, #06, #10, #12, #14, #17, #23, #25, #27, #31...).
- Florent Latifi: accounts, storage, reports, integration (#07, #11, #18, #19, #21, #26, #36...).
- Erti Hoxha: documentation, filters, exports, project management (#08, #09, #15, #16, #24...).
- Review rotation: Erti reviews Isa, Isa reviews Florent, Florent reviews Erti.

## Workflow rules from the plan

- Use only `main`. Never force-push. Pull before working and again before pushing.
- Show the diff and test results to the reviewer before pushing. Use small commits with clear messages.
- Checks before pushing: `ruff check`, `mypy pft`, `pytest --cov`; in `frontend/`: `npm run lint`, `npm run build`.
- Use synthetic data only. Keep public Python code typed and documented.
- Each task writes defense notes in `docs/defense/task-NN-<topic>.md`.

## Architecture (Appendix B)

- `pft/domain/`: entities, Money, transactions, validators, enums, exceptions.
  `pft/domain/exceptions.py` must not import anything from `pft`.
- `pft/services/`: Ledger, filters, reports, budget monitoring.
- `pft/infrastructure/`: SQLite repository and exporters.
- `pft/api/`: FastAPI routes and DTO mapping.
- `frontend/`: Vite + React + Recharts. Screens: Dashboard, Transactions, Budgets, Accounts.
- Data rules: ISO dates; amounts are positive and the kind/direction gives the sign; amounts travel as
  decimal strings and are stored as integer cents or decimal text; totals are calculated on the server.

## Team decisions

- Task #10, agreed 12 Nov 2026:
  - Enums are `StrEnum` with lowercase values (e.g. `Category.FOOD == "food"`).
  - The hierarchy includes `InvalidCategoryError`, raised by `from_text`.
  - API errors have the shape `{code, message, field}`. Every `FinanceError` subclass has a stable
    `code` class attribute (e.g. `"invalid_amount"`).
  - React label maps in `frontend/src/lib/labels.js` are keyed by these exact values.
