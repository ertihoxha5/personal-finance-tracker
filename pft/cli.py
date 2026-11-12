"""Command-line interface: ``python -m pft <command>`` (#21, FR-22, FR-23).

This is the outermost layer. It reads what the user typed, asks the Repository for the Ledger,
calls the domain and services, saves after every change, and prints the result. The domain and
services never print; only this file does.

Every ``FinanceError`` is turned into one friendly line on stderr and exit code 1, so the user
never sees a Python traceback for bad input. argparse reports usage mistakes itself (exit 2),
and ``--help`` works for every command.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence

from pft.domain.account import Account
from pft.domain.category import AccountType, Category, Kind
from pft.domain.exceptions import (
    AccountNotFoundError,
    FinanceError,
    InvalidAmountError,
    InvalidChoiceError,
)
from pft.domain.factory import TransactionFactory
from pft.domain.money import Money
from pft.domain.transaction import Transaction
from pft.infrastructure.repository import Repository, SqliteRepository
from pft.services.filters import (
    Predicate,
    apply_filters,
    by_account,
    by_category,
    by_kind,
    month_preset,
    sort_transactions,
    text_contains,
)
from pft.services.ledger import Ledger
from pft.services.reports import MonthlySummary, parse_month


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pft", description="Personal Finance Tracker")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    init = sub.add_parser("init", help="create the SQLite database (safe to re-run)")
    init.add_argument("--seed", action="store_true", help="insert demo data if empty")

    sub.add_parser("serve", help="run the API on http://127.0.0.1:8000")

    account = sub.add_parser("account", help="add or list accounts")
    account_sub = account.add_subparsers(dest="account_command", required=True, metavar="action")
    add_account = account_sub.add_parser("add", help="open a new account")
    add_account.add_argument("name", help="account name, for example Wallet")
    add_account.add_argument(
        "--type", default="bank", help="cash, bank, card or savings (default: bank)"
    )
    add_account.add_argument(
        "--opening", default="0", help="opening balance, for example 120.00 (default: 0)"
    )
    account_sub.add_parser("list", help="list accounts with their balances")

    add = sub.add_parser("add", help="add an income or expense")
    add.add_argument("kind", metavar="{income,expense}", help="income or expense")
    add.add_argument("amount", help="positive amount, for example 12.50")
    add.add_argument("category", help="for example food, rent, salary (not case sensitive)")
    add.add_argument("--account", help="account name or ID (optional if you have only one)")
    add.add_argument("--date", help="YYYY-MM-DD (default: today)")
    add.add_argument("--note", default="", help="a short note")

    listing = sub.add_parser("list", help="list transactions (filters combine with AND)")
    listing.add_argument("--account", help="account name or ID")
    listing.add_argument("--kind", help="income, expense or transfer")
    listing.add_argument("--category", action="append", help="repeat for several categories")
    listing.add_argument("--month", help="YYYY-MM")
    listing.add_argument("--search", help="text in the note")
    listing.add_argument("--sort", default="date", help="date, amount or category (default: date)")
    listing.add_argument("--desc", action="store_true", help="largest or newest first")

    balance = sub.add_parser("balance", help="show account balances and net worth")
    balance.add_argument("--account", help="account name or ID (default: all)")

    report = sub.add_parser("report", help="show a report")
    report_sub = report.add_subparsers(dest="report_type", required=True, metavar="type")
    monthly = report_sub.add_parser(
        "monthly", help="income, expenses, savings rate, top categories"
    )
    monthly.add_argument("--month", help="YYYY-MM (default: this month)")
    return parser


# --- helpers ------------------------------------------------------------------------------


def _money(text: str) -> str:
    """Money for display: 1234.5 -> '1234.50 EUR'."""
    return f"{text} EUR"


def _find_account(ledger: Ledger, reference: str | None) -> Account:
    """Find an account by ID or by name (any case). No reference works with a single account."""
    accounts = ledger.accounts
    if reference is None:
        if len(accounts) == 1:
            return accounts[0]
        if not accounts:
            raise AccountNotFoundError(
                "there are no accounts yet; create one with: pft account add NAME", field="account"
            )
        names = ", ".join(a.name for a in accounts)
        raise AccountNotFoundError(f"choose an account with --account ({names})", field="account")
    wanted = reference.strip()
    if wanted.isdigit():
        for account in accounts:
            if account.id == int(wanted):
                return account
    for account in accounts:
        if account.name.casefold() == wanted.casefold():
            return account
    raise AccountNotFoundError(f"no account named {reference!r}", field="account")


def _parse_opening(text: str) -> Money:
    try:
        return Money.of(text.strip().replace(",", "."))
    except InvalidAmountError as exc:
        raise InvalidAmountError(
            f"invalid opening balance {text!r}; enter a number like 120.00", field="opening"
        ) from exc


def _transactions(ledger: Ledger) -> list[Transaction]:
    found = (t for t in ledger.all_transactions() if isinstance(t, Transaction))
    return sorted(found, key=lambda t: t.id)


def _print_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], right: Sequence[int] = ()
) -> None:
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)
    ]

    def line(cells: Sequence[str]) -> str:
        parts = [
            cell.rjust(widths[i]) if i in right else cell.ljust(widths[i])
            for i, cell in enumerate(cells)
        ]
        return "  ".join(parts).rstrip()

    print(line(headers))
    print(line(["-" * w for w in widths]))
    for row in rows:
        print(line(row))


# --- commands -----------------------------------------------------------------------------


def _cmd_account_add(repo: Repository, args: argparse.Namespace) -> None:
    ledger = repo.load()
    account = ledger.open_account(
        args.name, AccountType.from_text(args.type), _parse_opening(args.opening)
    )
    repo.save(ledger)
    print(
        f"Opened account {account.id}: {account.name} ({account.type.value}), "
        f"opening balance {_money(str(account.opening_balance.amount))}"
    )


def _cmd_account_list(repo: Repository, args: argparse.Namespace) -> None:
    accounts = repo.load().accounts
    if not accounts:
        print("No accounts yet. Add one with: pft account add NAME --type bank")
        return
    _print_table(
        ["ID", "NAME", "TYPE", "BALANCE"],
        [[str(a.id), a.name, a.type.value, _money(str(a.balance.amount))] for a in accounts],
        right=(0, 3),
    )


def _cmd_add(repo: Repository, args: argparse.Namespace) -> None:
    ledger = repo.load()
    account = _find_account(ledger, args.account)
    date = args.date or dt.date.today().isoformat()
    transaction = TransactionFactory.from_input(
        args.kind,
        args.amount,
        args.category,
        date,
        account.id,
        args.note,
        transaction_id=ledger.next_transaction_id(),
    )
    ledger.add_transaction(account.id, transaction)
    repo.save(ledger)
    print(
        f"Added {transaction.kind.value} {transaction.id}: "
        f"{_money(str(transaction.amount.amount))} {transaction.category.value} "
        f"on {transaction.date.isoformat()} in {account.name}. "
        f"Balance: {_money(str(account.balance.amount))}"
    )


def _cmd_list(repo: Repository, args: argparse.Namespace) -> None:
    ledger = repo.load()
    predicates: list[Predicate] = []
    if args.account is not None:
        predicates.append(by_account(_find_account(ledger, args.account).id))
    if args.kind:
        predicates.append(by_kind(Kind.from_text(args.kind)))
    if args.category:
        predicates.append(by_category(*(Category.from_text(c) for c in args.category)))
    if args.month:
        year, month = parse_month(args.month)
        predicates.append(month_preset(year, month)())
    if args.search:
        predicates.append(text_contains(args.search))
    try:
        rows = sort_transactions(
            apply_filters(_transactions(ledger), *predicates), args.sort, reverse=args.desc
        )
    except ValueError as exc:
        raise InvalidChoiceError(str(exc), field="sort") from exc
    if not rows:
        print("No matching transactions.")
        return
    names = {a.id: a.name for a in ledger.accounts}
    _print_table(
        ["ID", "DATE", "ACCOUNT", "TYPE", "CATEGORY", "AMOUNT", "NOTE"],
        [
            [
                str(t.id),
                t.date.isoformat(),
                names[t.account_id],
                t.kind.value,
                t.category.value,
                f"{t.signed_amount().amount:+}",
                t.note,
            ]
            for t in rows
        ],
        right=(0, 5),
    )
    print(f"{len(rows)} transaction(s)")


def _cmd_balance(repo: Repository, args: argparse.Namespace) -> None:
    ledger = repo.load()
    if args.account is not None:
        account = _find_account(ledger, args.account)
        print(f"{account.name}: {_money(str(account.balance.amount))}")
        return
    _cmd_account_list(repo, args)
    if ledger.accounts:
        print(f"Net worth: {_money(str(ledger.net_worth.amount))}")


def _cmd_report_monthly(repo: Repository, args: argparse.Namespace) -> None:
    today = dt.date.today()
    year, month = parse_month(args.month) if args.month else (today.year, today.month)
    data = MonthlySummary(repo.load(), year, month).build()
    totals, previous = data.totals, data.previous
    print(f"Monthly summary {year}-{month:02d}")
    print(f"  Income:        {_money(str(totals.income.amount))}")
    print(f"  Expenses:      {_money(str(totals.expenses.amount))}")
    print(f"  Net:           {_money(str(totals.net.amount))}")
    print(f"  Savings rate:  {totals.savings_rate}%")
    if data.top_categories:
        print("  Top spending categories:")
        for rank, item in enumerate(data.top_categories, start=1):
            print(f"    {rank}. {item.category.value}: {_money(str(item.total.amount))}")
    else:
        print("  No spending this month.")
    label = f"{data.previous_year}-{data.previous_month:02d}"
    if previous.transaction_count == 0:
        print(f"  Compared with {label}: no data")
    else:
        change = data.net_change.amount
        print(
            f"  Compared with {label}: net {change:+} EUR "
            f"(income {data.income_change.amount:+}, expenses {data.expenses_change.amount:+})"
        )


def _run(args: argparse.Namespace) -> None:
    repo = SqliteRepository()
    match args.command:
        case "init":
            from pft.infrastructure.db import init_db

            print(f"Database ready at {init_db(seed=args.seed)}")
        case "serve":
            from pft.api.main import run

            run()
        case "account":
            match args.account_command:
                case "add":
                    _cmd_account_add(repo, args)
                case "list":
                    _cmd_account_list(repo, args)
        case "add":
            _cmd_add(repo, args)
        case "list":
            _cmd_list(repo, args)
        case "balance":
            _cmd_balance(repo, args)
        case "report":
            match args.report_type:
                case "monthly":
                    _cmd_report_monthly(repo, args)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command. Returns 0 on success and 1 when a FinanceError was reported."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _run(args)
    except FinanceError as error:
        print(f"Error: {error.message}", file=sys.stderr)
        return 1
    return 0


__all__ = ["build_parser", "main"]
