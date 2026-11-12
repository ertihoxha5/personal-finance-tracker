"""Reusable validation rules: descriptors and decorators (#12, FR-23).

Each rule is written once and reused everywhere:

- ``PositiveAmount`` and ``NonEmptyText`` are data descriptors. Declared on a
  class, they check every assignment to that attribute, including the one in
  ``__init__``, so an object can never hold an invalid value.
- ``@require_positive`` applies the same positive-amount rule to a function's
  ``amount`` argument.
- ``@log_action("add")`` writes exactly one log line per call: INFO after
  success, WARNING (then re-raise) after a failure.

PositiveAmount and @require_positive both call ``_ensure_positive``, so the
rule and its message exist in one place only.

Dataclass compatibility (for #14 Transaction and Account):

- Annotate the field with the descriptor type and use the descriptor as its
  default: ``amount: PositiveAmount = PositiveAmount()``. mypy then types
  ``__init__``'s parameter and ``obj.amount`` as Money. On class access
  ``__get__`` raises AttributeError, so ``dataclass`` sees no default and the
  field stays required at runtime (mypy alone still thinks it has a default).
- Do not use ``slots=True``: the descriptors store the value in the instance
  ``__dict__`` under ``_<name>``, and a slotted class has no ``__dict__``.
- ``frozen=True`` works: the frozen ``__init__`` assigns through
  ``object.__setattr__``, which still calls the descriptor, and the descriptor
  writes straight into ``__dict__``. Later assignments are blocked by the
  frozen ``__setattr__`` before the descriptor runs.

This module only creates a logger. Handlers, levels and the log file are
configured once at the entry point (CLI or API), so importing this module or
running the tests has no side effects.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Generic, ParamSpec, TypeVar

from pft.domain.exceptions import FinanceError, InvalidAmountError, InvalidTextError
from pft.domain.money import Money

log = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


def _ensure_positive(value: object, name: str) -> Money:
    """Return ``value`` if it is Money greater than zero, else raise InvalidAmountError."""
    if not isinstance(value, Money):
        raise InvalidAmountError(
            f"{name} must be a Money value, got {type(value).__name__}", field=name
        )
    if value.amount <= 0:
        raise InvalidAmountError(
            f"{name} must be greater than zero, got {value.amount}", field=name
        )
    return value


class _Validated(Generic[T]):
    """Base data descriptor: validates on every assignment, stores on the instance."""

    public_name: str
    private_name: str

    def __set_name__(self, owner: type, name: str) -> None:
        # Called once when the owning class is created, e.g. name == "amount".
        self.public_name = name
        self.private_name = "_" + name

    def __get__(self, obj: object | None, objtype: type | None = None) -> T:
        if obj is None:
            # Class access. Returning self here would make a dataclass use the
            # descriptor object as the field's default value.
            raise AttributeError(f"{self.public_name} is only available on instances")
        try:
            value: T = vars(obj)[self.private_name]
        except KeyError:
            raise AttributeError(f"{self.public_name} has not been set") from None
        return value

    def __set__(self, obj: object, value: T) -> None:
        # The value lives on the instance, never on the descriptor, which is
        # shared by every instance of the class.
        vars(obj)[self.private_name] = self._validate(value)

    def _validate(self, value: object) -> T:  # pragma: no cover - overridden by subclasses
        raise NotImplementedError


class PositiveAmount(_Validated[Money]):
    """Descriptor for a Money attribute that must be greater than zero."""

    def _validate(self, value: object) -> Money:
        return _ensure_positive(value, self.public_name)


class NonEmptyText(_Validated[str]):
    """Descriptor for a text attribute that must not be empty or only whitespace.

    The stored value is stripped. ``error`` picks the FinanceError subclass to
    raise, so Account can keep raising InvalidAccountNameError.
    """

    def __init__(self, error: type[FinanceError] = InvalidTextError) -> None:
        self.error = error

    def _validate(self, value: object) -> str:
        if not isinstance(value, str):
            raise self.error(
                f"{self.public_name} must be text, got {type(value).__name__}",
                field=self.public_name,
            )
        cleaned = value.strip()
        if not cleaned:
            raise self.error(f"{self.public_name} must not be empty", field=self.public_name)
        return cleaned


def log_action(action: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator factory: log one line per call of the decorated function.

    ``@log_action("add")`` logs ``add: <function>`` at INFO after a successful
    call. If the function raises, it logs ``add failed: <function> (<error type>)``
    at WARNING and re-raises. Only the action and function are logged, never the
    arguments, so amounts and notes stay out of the log.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                log.warning("%s failed: %s (%s)", action, func.__qualname__, type(exc).__name__)
                raise
            log.info("%s: %s", action, func.__qualname__)
            return result

        return wrapper

    return decorator


def require_positive(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator: reject a call whose ``amount`` argument is not positive Money.

    The argument is found through the function's signature, so it works whether
    ``amount`` is passed by position or by keyword. Decorating a function that
    has no ``amount`` parameter is a TypeError at import time, not at call time.
    """
    signature = inspect.signature(func)
    if "amount" not in signature.parameters:
        raise TypeError(f"@require_positive needs an 'amount' parameter on {func.__qualname__}")

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        _ensure_positive(bound.arguments["amount"], "amount")
        return func(*args, **kwargs)

    return wrapper


__all__: list[str] = [
    "NonEmptyText",
    "PositiveAmount",
    "log_action",
    "require_positive",
]
