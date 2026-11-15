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
from collections.abc import Iterable, Sequence
from pathlib import Path

from pft.domain.account import Account
from pft.domain.budget import BUDGET_WARNING, Budget, level_percent
from pft.domain.category import AccountType, Category, Kind
from pft.domain.exceptions import (
    AccountNotFoundError,
    FinanceError,
    InvalidAmountError,
    InvalidChoiceError,
    StorageError,
)
from pft.domain.factory import TransactionFactory
from pft.domain.money import Money
from pft.domain.transaction import Transaction
from pft.infrastructure.exporters import Exporter, ExportRow
from pft.infrastructure.repository import Repository, SqliteRepository
from pft.services.budget_monitor import BudgetMonitor, BudgetWarning
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

    budget = sub.add_parser("budget", help="set or list monthly budgets")
    budget_sub = budget.add_subparsers(dest="budget_command", required=True, metavar="action")
    set_budget = budget_sub.add_parser("set", help="set the limit for a category and month")
    set_budget.add_argument("category", help="for example food")
    set_budget.add_argument("limit", help="monthly limit, for example 200.00")
    set_budget.add_argument("--month", help="YYYY-MM (default: this month)")
    list_budgets = budget_sub.add_parser("list", help="show budgets with their usage")
    list_budgets.add_argument("--month", help="YYYY-MM (default: this month)")

    balance = sub.add_parser("balance", help="show account balances and net worth")
    balance.add_argument("--account", help="account name or ID (default: all)")

    report = sub.add_parser("report", help="show a report")
    report_sub = report.add_subparsers(dest="report_type", required=True, metavar="type")
    monthly = report_sub.add_parser(
        "monthly", help="income, expenses, savings rate, top categories"
    )
    monthly.add_argument("--month", help="YYYY-MM (default: this month)")
    monthly.add_argument("period", nargs="?", help="YYYY-MM (alternative to --month)")
    monthly.add_argument(
        "--export", metavar="FORMAT", help="write using a registered export format"
    )
    monthly.add_argument(
        "--out", help="destination filename (default: monthly-report-MONTH.FORMAT)"
    )

    export = sub.add_parser("export", help="export stored data to a file")
    export_sub = export.add_subparsers(dest="export_type", required=True, metavar="type")
    transactions = export_sub.add_parser("transactions", help="export all stored transactions")
    transactions.add_argument("--format", required=True, help="registered export format")
    transactions.add_argument("--out", required=True, help="destination filename")
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
    # The monitor is an Observer of the Ledger (#27). It only collects warnings; printing
    # stays in this file, after the change was saved.
    warnings: list[BudgetWarning] = []
    ledger.subscribe(BudgetMonitor(ledger, repo.load_budgets(), warnings.append))
    ledger.add_transaction(account.id, transaction)
    repo.save(ledger)
    print(
        f"Added {transaction.kind.value} {transaction.id}: "
        f"{_money(str(transaction.amount.amount))} {transaction.category.value} "
        f"on {transaction.date.isoformat()} in {account.name}. "
        f"Balance: {_money(str(account.balance.amount))}"
    )
    for warning in warnings:
        print(f"Warning: {warning.message}")


def _this_month() -> str:
    return dt.date.today().strftime("%Y-%m")


def _cmd_budget_set(repo: Repository, args: argparse.Namespace) -> None:
    try:
        limit = Money.of(args.limit.strip().replace(",", "."))
    except InvalidAmountError as exc:
        raise InvalidAmountError(
            f"invalid limit {args.limit!r}; enter a number like 200.00", field="limit"
        ) from exc
    budget = Budget(Category.from_text(args.category), args.month or _this_month(), limit)
    others = [
        b for b in repo.load_budgets() if (b.category, b.month) != (budget.category, budget.month)
    ]
    repo.save_budgets([*others, budget])
    print(
        f"Budget set: {budget.category.value} {budget.month}, "
        f"limit {_money(str(budget.limit.amount))}"
    )


def _cmd_budget_list(repo: Repository, args: argparse.Namespace) -> None:
    month = args.month or _this_month()
    budgets = sorted(
        (b for b in repo.load_budgets() if b.month == month), key=lambda b: b.category.value
    )
    if not budgets:
        print(f"No budgets for {month}. Set one with: pft budget set food 200")
        return
    ledger = repo.load()
    rows = []
    for budget in budgets:
        spent = budget.spent(ledger)
        level = budget.level_reached(spent)
        if level is None:
            status = "ok"
        else:
            status = f"exceeded ({level_percent(level)}% reached)"
            if level == BUDGET_WARNING:
                status = f"warning ({level_percent(level)}% reached)"
        rows.append(
            [
                budget.category.value,
                _money(str(budget.limit.amount)),
                _money(str(spent.amount)),
                f"{int(budget.percent_of(spent))}%",
                status,
            ]
        )
    print(f"Budgets {month}")
    _print_table(["CATEGORY", "LIMIT", "SPENT", "USED", "STATUS"], rows, right=(1, 2, 3))


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
    if args.period and args.month and args.period != args.month:
        raise InvalidChoiceError(
            "Use one month: the positional month and --month disagree.", field="month"
        )
    if args.out and not args.export:
        raise InvalidChoiceError("--out requires --export FORMAT.", field="out")
    today = dt.date.today()
    chosen = args.period or args.month
    year, month = parse_month(chosen) if chosen else (today.year, today.month)
    data = MonthlySummary(repo.load(), year, month).build()
    totals, previous = data.totals, data.previous
    if args.export:
        period = f"{year:04d}-{month:02d}"
        rows: list[dict[str, object]] = [
            {"month": period, "section": "summary", "label": label, "value": value, "unit": unit}
            for label, value, unit in (
                ("income", totals.income, totals.income.currency),
                ("expenses", totals.expenses, totals.expenses.currency),
                ("net", totals.net, totals.net.currency),
                ("savingsRate", totals.savings_rate, "%"),
            )
        ]
        rows.extend(
            {
                "month": period,
                "section": "category",
                "label": item.category.value,
                "value": item.total,
                "unit": item.total.currency,
            }
            for item in data.categories
        )
        output = args.out or f"monthly-report-{period}.{args.export.strip().lower()}"
        path = _export_file(rows, args.export, output)
        print(f"Exported monthly report to {path}")
        return
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


def _export_file(rows: Iterable[ExportRow], fmt: str, output: str) -> Path:
    """Shared registry lookup; no concrete exporter or format branching (#32)."""
    try:
        exporter = Exporter.for_format(fmt)
    except ValueError as exc:
        raise InvalidChoiceError(str(exc), field="format") from exc
    try:
        path = Path(output).expanduser().resolve()
        exporter.export(rows, path)
    except OSError as exc:
        raise StorageError(
            f"Could not write export to {output}: {exc.strerror or str(exc)}"
        ) from exc
    except ValueError as exc:
        raise StorageError(f"Could not create export: {exc}") from exc
    return path


def _cmd_export_transactions(repo: Repository, args: argparse.Namespace) -> None:
    """Registry lookup keeps CLI code independent of concrete formats (#32)."""
    path = _export_file(
        (transaction.to_row() for transaction in _transactions(repo.load())), args.format, args.out
    )
    print(f"Exported transactions to {path}")


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
        case "budget":
            match args.budget_command:
                case "set":
                    _cmd_budget_set(repo, args)
                case "list":
                    _cmd_budget_list(repo, args)
        case "balance":
            _cmd_balance(repo, args)
        case "report":
            match args.report_type:
                case "monthly":
                    _cmd_report_monthly(repo, args)
        case "export":
            match args.export_type:
                case "transactions":
                    _cmd_export_transactions(repo, args)


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
