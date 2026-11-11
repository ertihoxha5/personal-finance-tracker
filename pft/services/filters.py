"""Composable transaction predicates for task #08.

The structural interface follows #14's planned Transaction fields without
requiring that class or #10's enums to exist yet. Enum members can be passed
directly to the category and kind builders once those tasks are integrated.
"""

from collections.abc import Callable
from datetime import date
from typing import Protocol

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
