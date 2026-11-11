"""Domain exceptions.

Pulled forward from task #10 so the Money value object raises the real types;
#10 adds the remaining exceptions to this module.
"""


class FinanceError(Exception):
    """Base class for every error raised by the finance domain."""


class InvalidAmountError(FinanceError):
    """An amount is not a valid, finite money value."""


class InvalidCurrencyError(FinanceError):
    """A currency is not a three-letter upper-case code such as 'EUR'."""


class CurrencyMismatchError(FinanceError):
    """Two money values in different currencies were combined or compared."""


class TransactionNotFoundError(FinanceError):
    """No transaction with the requested ID exists in the account."""


class DuplicateTransactionError(FinanceError):
    """A transaction with the same ID is already in the account."""


class TransactionIdChangedError(FinanceError):
    """An edit tried to give a transaction a different ID."""


class InvalidAccountNameError(FinanceError):
    """An account name is empty or only whitespace."""
