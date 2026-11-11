"""Composable transaction predicates for task #08.

The structural interface follows #14's planned Transaction fields without
requiring that class or #10's enums to exist yet. Enum members can be passed
directly to the category and kind builders once those tasks are integrated.
"""

from calendar import monthrange
from collections.abc import Callable, Iterable, Iterator
from datetime import date
from functools import partial
from typing import Protocol, TypeVar

from pft.domain.money import Money


class FilterableTransaction(Protocol):
    """Read-only transaction fields needed by the filter builders."""

    @property
    def category(self) -> object: ...

    @property
    def kind(self) -> object: ...

    @property
    def account_id(self) -> int: ...

    @property
    def date(self) -> date: ...

    @property
    def amount(self) -> Money: ...


Predicate = Callable[[FilterableTransaction], bool]
TransactionT = TypeVar("TransactionT", bound=FilterableTransaction)


def by_category(*cats: object) -> Predicate:
    """Match any supplied category; no categories matches nothing."""
    return lambda transaction: transaction.category in cats


def by_kind(kind: object) -> Predicate:
    """Match a transaction kind, such as income or expense."""
    return lambda transaction: transaction.kind == kind


def by_account(account_id: int) -> Predicate:
    """Match the owning account's stable ID."""
    return lambda transaction: transaction.account_id == account_id


def between(start: date, end: date) -> Predicate:
    """Match dates inclusively; reject a reversed range."""
    if start > end:
        raise ValueError("start date must be on or before end date")
    return lambda transaction: start <= transaction.date <= end


def amount_between(lo: Money, hi: Money) -> Predicate:
    """Match inclusive amount magnitudes, using #14's unsigned Money field.

    Money enforces matching currencies for bounds and transactions. Direction
    belongs to the kind filter; expenses still have positive amount fields.
    """
    if lo > hi:
        raise ValueError("minimum amount must not exceed maximum amount")
    return lambda transaction: lo <= transaction.amount <= hi


def all_of(*preds: Predicate) -> Predicate:
    """Require every predicate, short-circuiting; no predicates accepts all."""
    return lambda transaction: all(predicate(transaction) for predicate in preds)


def any_of(*preds: Predicate) -> Predicate:
    """Require at least one predicate, short-circuiting; no predicates rejects all."""
    return lambda transaction: any(predicate(transaction) for predicate in preds)


def apply_filters(items: Iterable[TransactionT], *preds: Predicate) -> Iterator[TransactionT]:
    """Return a lazy generator preserving input order, identity and concrete type.

    Predicates combine with AND. With no predicates, every item passes. The
    input is consumed only as the caller advances the returned generator.
    """
    combined = all_of(*preds)
    return (transaction for transaction in items if combined(transaction))


def month_preset(year: int, month: int) -> partial[Predicate]:
    """Bind inclusive month boundaries into a reusable predicate factory.

    For example, ``this_month = month_preset(2026, 11)`` then
    ``apply_filters(items, this_month())``. Callers choose the month explicitly
    so a long-running process never relies on an import-time current date.
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    return partial(between, first_day, last_day)
