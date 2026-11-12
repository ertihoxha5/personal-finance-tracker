import ast
from pathlib import Path

import pytest

import pft.domain.exceptions as exceptions_module
from pft.domain.exceptions import (
    AccountNotFoundError,
    BudgetError,
    CurrencyMismatchError,
    DataImportError,
    FinanceError,
    InvalidAmountError,
    InvalidCategoryError,
    InvalidDateError,
    TransactionNotFoundError,
)


def all_finance_errors() -> list[type[FinanceError]]:
    found: list[type[FinanceError]] = []
    pending = [FinanceError]
    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())
    return found


PLAN_ERRORS = [
    InvalidAmountError,
    InvalidDateError,
    AccountNotFoundError,
    TransactionNotFoundError,
    CurrencyMismatchError,
    BudgetError,
    DataImportError,
    InvalidCategoryError,
]


@pytest.mark.parametrize("error", PLAN_ERRORS, ids=lambda cls: cls.__name__)
def test_every_custom_error_is_a_finance_error(error: type[FinanceError]) -> None:
    assert issubclass(error, FinanceError)
    with pytest.raises(FinanceError):
        raise error("synthetic failure")


@pytest.mark.parametrize("error", all_finance_errors(), ids=lambda cls: cls.__name__)
def test_every_error_has_a_docstring_and_its_own_snake_case_code(
    error: type[FinanceError],
) -> None:
    assert error.__doc__
    assert error.code == error.code.lower()
    assert " " not in error.code
    assert "code" in vars(error), f"{error.__name__} inherits its code"


def test_codes_are_unique() -> None:
    codes = [error.code for error in all_finance_errors()]
    assert len(codes) == len(set(codes))


def test_to_dict_has_the_api_error_shape() -> None:
    error = InvalidAmountError("enter an amount greater than zero", field="amount")
    assert error.to_dict() == {
        "code": "invalid_amount",
        "message": "enter an amount greater than zero",
        "field": "amount",
    }
    assert str(error) == "enter an amount greater than zero"


def test_field_defaults_to_none_for_page_level_errors() -> None:
    assert AccountNotFoundError("account 7 does not exist").to_dict()["field"] is None


def test_exceptions_module_imports_nothing_from_pft() -> None:
    tree = ast.parse(Path(exceptions_module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not [name for name in imported if name == "pft" or name.startswith("pft.")]
