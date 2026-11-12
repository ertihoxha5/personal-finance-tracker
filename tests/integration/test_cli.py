"""CLI tests (#21). Each call to main() is a fresh program start on the same database file."""

from collections.abc import Callable
from pathlib import Path

import pytest

from pft.cli import build_parser, main
from pft.infrastructure import db

Run = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Run:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "cli.sqlite3"))

    def call(*argv: str) -> tuple[int, str, str]:
        code = main(list(argv))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return call


def test_add_expense_is_still_there_after_a_restart(run: Run) -> None:
    assert run("account", "add", "Cash", "--type", "cash", "--opening", "100")[0] == 0

    code, out, _ = run(
        "add", "expense", "12.50", "FOOD", "--account", "cash", "--date", "2026-11-10"
    )
    assert code == 0
    assert "Balance: 87.50 EUR" in out

    # Every run() is a new load from the database file, like starting the program again.
    code, out, _ = run("list")
    assert code == 0 and "food" in out and "-12.50" in out
    assert "Cash: 87.50 EUR" in run("balance", "--account", "cash")[1]


def test_account_add_and_list_show_balances_and_net_worth(run: Run) -> None:
    run("account", "add", "Bank", "--opening", "1000")
    run("account", "add", "Wallet", "--type", "cash", "--opening", "20.50")
    out = run("account", "list")[1]
    assert "Bank" in out and "1000.00 EUR" in out and "Wallet" in out
    assert "Net worth: 1020.50 EUR" in run("balance")[1]


def test_list_filters_and_sorting(run: Run) -> None:
    run("account", "add", "Bank", "--opening", "0")
    run("add", "income", "800", "salary", "--date", "2026-11-01", "--note", "Pay")
    run("add", "expense", "60", "food", "--date", "2026-11-02", "--note", "Lunch out")
    run("add", "expense", "600", "rent", "--date", "2026-10-03")

    out = run("list", "--kind", "expense", "--month", "2026-11")[1]
    assert "Lunch out" in out and "rent" not in out and "1 transaction(s)" in out
    assert run("list", "--search", "PAY")[1].count("income") == 1
    both = ("list", "--category", "food", "--category", "rent")
    largest_first = run(*both, "--sort", "amount", "--desc")[1]
    smallest_first = run(*both, "--sort", "amount")[1]
    assert largest_first.index("rent") < largest_first.index("food")
    assert smallest_first.index("food") < smallest_first.index("rent")
    assert "No matching transactions." in run("list", "--month", "2020-01")[1]


def test_report_monthly_matches_the_plan_example(run: Run) -> None:
    run("account", "add", "Bank")
    run("add", "income", "800", "salary", "--date", "2026-11-01")
    run("add", "expense", "600", "rent", "--date", "2026-11-02")
    code, out, _ = run("report", "monthly", "--month", "2026-11")
    assert code == 0
    assert "Net:           200.00 EUR" in out
    assert "Savings rate:  25.0%" in out
    assert "1. rent: 600.00 EUR" in out
    assert "Compared with 2026-10: no data" in out


@pytest.mark.parametrize(
    "argv",
    [
        ("add", "expense", "abc", "food"),  # not a number
        ("add", "expense", "-5", "food"),  # must be positive
        ("add", "expense", "5", "nope"),  # unknown category
        ("add", "expense", "5", "food", "--date", "2026-13-40"),
        ("add", "transfer", "5", "food"),  # transfers are a linked pair
        ("add", "refund", "5", "food"),
        ("add", "expense", "5", "food", "--account", "ghost"),
        ("account", "add", "  "),
        ("account", "add", "X", "--type", "yacht"),
        ("account", "add", "X", "--opening", "lots"),
        ("list", "--kind", "gift"),
        ("list", "--month", "nov"),
        ("list", "--sort", "colour"),
        ("report", "monthly", "--month", "2026-00"),
    ],
)
def test_invalid_input_gives_a_friendly_error_and_no_traceback(
    run: Run, argv: tuple[str, ...]
) -> None:
    run("account", "add", "Bank")
    code, out, err = run(*argv)
    assert code == 1
    assert err.startswith("Error: ")
    assert "Traceback" not in out + err
    assert out == ""


def test_a_failed_command_changes_nothing(run: Run) -> None:
    run("account", "add", "Bank", "--opening", "10")
    assert run("add", "expense", "abc", "food")[0] == 1
    assert "Bank" in run("balance")[1] and "10.00 EUR" in run("balance")[1]
    assert "No matching transactions." in run("list")[1]


def test_no_accounts_gives_a_hint_instead_of_a_crash(run: Run) -> None:
    code, _, err = run("add", "expense", "5", "food")
    assert code == 1 and "pft account add" in err
    assert "No accounts yet" in run("account", "list")[1]


def test_several_accounts_require_account_choice(run: Run) -> None:
    run("account", "add", "A")
    run("account", "add", "B")
    code, _, err = run("add", "expense", "5", "food")
    assert code == 1 and "--account (A, B)" in err
    assert run("add", "expense", "5", "food", "--account", "2")[0] == 0  # by ID


def _subcommands() -> list[list[str]]:
    return [
        [],
        ["init"],
        ["serve"],
        ["account"],
        ["account", "add"],
        ["account", "list"],
        ["add"],
        ["list"],
        ["balance"],
        ["report"],
        ["report", "monthly"],
    ]


@pytest.mark.parametrize("path", _subcommands(), ids=lambda p: " ".join(p) or "pft")
def test_help_works_everywhere(path: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        build_parser().parse_args([*path, "--help"])
    assert stop.value.code == 0
    assert "usage: pft" in capsys.readouterr().out


def test_missing_command_is_a_usage_error_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as stop:
        main([])
    assert stop.value.code == 2
    assert "usage: pft" in capsys.readouterr().err
