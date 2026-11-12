"""Entry point for ``python -m pft`` and the ``pft`` script. The commands live in pft/cli.py."""

from __future__ import annotations

from pft.cli import build_parser, main

__all__ = ["build_parser", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
