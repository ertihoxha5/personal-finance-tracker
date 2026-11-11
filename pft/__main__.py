"""Command-line entry point: ``python -m pft <command>``."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pft", description="Personal Finance Tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create the SQLite database (safe to re-run)")
    init.add_argument("--seed", action="store_true", help="insert demo data if empty")

    sub.add_parser("serve", help="run the API on http://127.0.0.1:8000")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        from pft.infrastructure.db import init_db

        path = init_db(seed=args.seed)
        print(f"Database ready at {path}")
    elif args.command == "serve":
        from pft.api.main import run

        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
