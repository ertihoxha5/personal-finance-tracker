"""Domain exceptions.

Every error the finance domain raises is a FinanceError, so the CLI and the API
can catch that one type and show a readable message instead of a traceback
(FR-23). Each class has a stable ``code`` that the API sends to React as
``{code, message, field}``; ``field`` names the input the error belongs to, or
is None for errors that concern the whole page.

This module imports nothing from ``pft`` so any module can import it without
creating an import cycle.
"""

from __future__ import annotations

from typing import ClassVar


class FinanceError(Exception):
    """Base class for every error raised by the finance domain."""

    code: ClassVar[str] = "finance_error"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, str | None]:
        """Return the API error shape: {code, message, field}."""
        return {"code": self.code, "message": self.message, "field": self.field}


class InvalidAmountError(FinanceError):
    """An amount is not a valid, finite money value."""

    code = "invalid_amount"


class InvalidCurrencyError(FinanceError):
    """A currency is not a three-letter upper-case code such as 'EUR'."""

    code = "invalid_currency"


class CurrencyMismatchError(FinanceError):
    """Two money values in different currencies were combined or compared."""

    code = "currency_mismatch"


class InvalidDateError(FinanceError):
    """A date is missing, malformed or outside the allowed range."""

    code = "invalid_date"


class InvalidChoiceError(FinanceError):
    """A text value does not match any member of a fixed list such as Kind."""

    code = "invalid_choice"


class InvalidCategoryError(InvalidChoiceError):
    """A category name does not match any Category member."""

    code = "invalid_category"


class InvalidTextError(FinanceError):
    """A required text value is missing, empty or only whitespace."""

    code = "invalid_text"


class AccountNotFoundError(FinanceError):
    """No account with the requested ID exists."""

    code = "account_not_found"


class InvalidAccountNameError(FinanceError):
    """An account name is empty or only whitespace."""

    code = "invalid_account_name"


class TransactionNotFoundError(FinanceError):
    """No transaction with the requested ID exists in the account."""

    code = "transaction_not_found"


class DuplicateTransactionError(FinanceError):
    """A transaction with the same ID is already in the account."""

    code = "duplicate_transaction"


class TransactionIdChangedError(FinanceError):
    """An edit tried to give a transaction a different ID."""

    code = "transaction_id_changed"


class InvalidTransferError(FinanceError):
    """A transfer was used in a way it doesn't support, such as copying it for recurrence."""

    code = "invalid_transfer"


class BudgetError(FinanceError):
    """A budget is invalid, such as a non-positive limit or a duplicate month."""

    code = "budget_error"


class DataImportError(FinanceError):
    """Imported or stored data could not be read into domain objects."""

    code = "data_import_error"


class StorageError(FinanceError):
    """Saving or loading data failed; the previously saved data is unchanged."""

    code = "storage_error"
