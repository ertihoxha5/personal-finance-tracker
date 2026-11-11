# personal-finance-tracker

Advanced Programming Group Project: a local personal finance tracker with a Python
backend (FastAPI + SQLite, plus a CLI) and a React frontend.

## Prerequisites

| Tool   | Version |
| ------ | ------- |
| Python | 3.11+ (CI runs 3.11) |
| Node   | 22 (see `.nvmrc`) |
| npm    | 10+ |
| Git    | any recent 2.x |

On Windows, use the `py` launcher so the venv is built with 3.11, not the Microsoft Store
`python.exe` alias.

## Project layout

```
pft/                 Python package
  domain/            entities and business rules
  services/          use cases
  infrastructure/    SQLite access (db.py)
  api/               FastAPI app (main.py)
  __main__.py        CLI: python -m pft ...
tests/unit, tests/integration
frontend/            Vite + React (JavaScript)
```

## Backend setup

```bash
py -3.11 -m venv .venv          # macOS/Linux: python3.11 -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m pft init --seed       # create the database with demo data
python -m pft serve             # API on http://127.0.0.1:8000
```

Check it with `http://127.0.0.1:8000/api/health`, which returns `{"status": "ok"}`.
Interactive docs are at `/docs`.

## Frontend setup

In a second terminal, with the backend running:

```bash
cd frontend
npm ci
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `127.0.0.1:8000`, so the frontend and API share one
origin and no CORS setup is needed.

## Database

- Default location: `data/tracker.sqlite3` in the project root. The folder is created
  automatically and is git-ignored.
- Override it with the `PFT_DB_PATH` environment variable:
  - PowerShell: `$env:PFT_DB_PATH = "C:\temp\demo.sqlite3"`
  - bash: `export PFT_DB_PATH=/tmp/demo.sqlite3`
- `python -m pft init` is idempotent. Running it again never drops data, and `--seed` only
  inserts demo rows when the database is empty.
- Money is stored as integer cents (for example, `-6450` means -64.50), so there are no
  floating-point rounding errors.

### Demo reset

Stop the server, delete the database file, then initialise it again:

```bash
del data\tracker.sqlite3        # macOS/Linux: rm data/tracker.sqlite3
python -m pft init --seed
```

## Checks

```bash
ruff check . && ruff format --check .
mypy
pytest
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push to `main`.

## Design notes

**Why there is no authentication.** This is a single-user app that runs on the owner's own
machine. The API binds only to `127.0.0.1`, so other devices on the network can't reach it.
Adding logins would bring in password storage and session handling without protecting
anything the operating system's user account doesn't already protect.

**How data persists.** Everything is stored in one SQLite file on disk. Each write is
committed in a transaction, so it survives closing the app, restarting the server or
rebooting the machine. SQLite needs no separate database server, and backing up or
resetting the data means copying or deleting that one file.
