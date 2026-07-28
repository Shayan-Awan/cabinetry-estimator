"""Deterministic decimal handling for every monetary and quantity value.

Two rules hold everywhere in this application:

1. Money is never a ``float``. Binary floating point cannot represent values
   like ``0.10`` exactly, and the error compounds across a multi-line invoice.
2. Rounding happens in exactly one place, with one documented policy, at the
   moment a value becomes currency.

Storage
-------
SQLite has no decimal type, and SQLAlchemy's ``Numeric`` silently falls back to
``float`` on SQLite -- which would defeat rule 1 at the persistence layer. So
decimals are stored as **integers in minor units** (cents for money, and the
equivalent for rates and quantities at their own scales). Integers are exact,
sort correctly, and can be summed in SQL without ever becoming a float.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator

# --- Scales -----------------------------------------------------------------
# Decimal places carried by each kind of value.
MONEY_SCALE = 2  # dollars and cents
RATE_SCALE = 4  # unit rates; some equipment rates carry fractional cents
QUANTITY_SCALE = 3  # hours and material quantities
PERCENT_SCALE = 4  # GST and markup, stored as a fraction (0.05 == 5%)

MONEY_EXPONENT = Decimal(1).scaleb(-MONEY_SCALE)  # Decimal("0.01")

# The rounding policy for currency. Half-way values round away from zero, which
# is what invoices and Canadian tax remittance expect. ROUND_HALF_EVEN
# ("banker's rounding"), Python's default, would round 2.675 down to 2.67.
CURRENCY_ROUNDING = ROUND_HALF_UP

DEFAULT_CURRENCY = "CAD"


class MoneyError(ValueError):
    """Raised when a value cannot be handled exactly as a decimal."""


def to_decimal(value: Any) -> Decimal:
    """Coerce ``value`` to ``Decimal`` without ever passing through ``float``.

    ``float`` input is rejected on purpose: ``Decimal(0.1)`` is
    ``0.1000000000000000055511151231257827``, and accepting it here would let
    that error reach an invoice. Parse user text with :func:`parse_decimal`
    instead.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # bool is an int subclass; almost never intended
        raise MoneyError(f"Cannot use a boolean as a numeric value: {value!r}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return parse_decimal(value)
    if isinstance(value, float):
        raise MoneyError(
            "Refusing to convert a float to Decimal, because floats cannot "
            "represent currency exactly. Pass a str or Decimal instead "
            f"(got {value!r})."
        )
    raise MoneyError(f"Cannot convert {type(value).__name__} to Decimal: {value!r}")


def parse_decimal(text: str) -> Decimal:
    """Parse human-entered text such as ``"$1,234.50"`` into a ``Decimal``."""
    cleaned = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    if not cleaned:
        raise MoneyError("Expected a number, got an empty value.")
    try:
        return Decimal(cleaned)
    except ArithmeticError as exc:  # decimal.InvalidOperation
        raise MoneyError(f"{text!r} is not a valid number.") from exc


def quantize(value: Any, scale: int) -> Decimal:
    """Round ``value`` to ``scale`` decimal places using the currency policy."""
    return to_decimal(value).quantize(Decimal(1).scaleb(-scale), rounding=CURRENCY_ROUNDING)


def quantize_money(value: Any) -> Decimal:
    """Round to cents. This is the only place currency rounding should happen."""
    return quantize(value, MONEY_SCALE)


def quantize_quantity(value: Any) -> Decimal:
    return quantize(value, QUANTITY_SCALE)


def quantize_rate(value: Any) -> Decimal:
    return quantize(value, RATE_SCALE)


def format_money(value: Any, currency: str = DEFAULT_CURRENCY) -> str:
    """Render a value for display, e.g. ``$1,234.50``. Display only."""
    amount = quantize_money(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f} {currency}".strip()


class ScaledDecimal(TypeDecorator):
    """Stores a ``Decimal`` as an exact integer number of minor units.

    Subclasses fix ``scale``; the class attribute (rather than a constructor
    argument) keeps ``cache_ok`` sound for SQLAlchemy's compiled-statement
    cache.
    """

    impl = Integer
    cache_ok = True
    scale: int = 0

    @property
    def _factor(self) -> Decimal:
        return Decimal(10) ** self.scale

    def process_bind_param(self, value: Any, dialect: Any) -> int | None:
        if value is None:
            return None
        scaled = to_decimal(value) * self._factor
        if scaled != scaled.to_integral_value():
            # Silently rounding here would hide a real decision -- for example
            # a rate entered with more precision than the column carries.
            raise MoneyError(
                f"{value} has more than {self.scale} decimal places and cannot "
                f"be stored exactly. Round it explicitly first."
            )
        return int(scaled)

    def process_result_value(self, value: Any, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        return (Decimal(value) / self._factor).quantize(Decimal(1).scaleb(-self.scale))


class Money(ScaledDecimal):
    """Currency amounts, stored as cents."""

    scale = MONEY_SCALE


class Rate(ScaledDecimal):
    """Unit rates, stored to four decimal places."""

    scale = RATE_SCALE


class Quantity(ScaledDecimal):
    """Hours and material quantities, stored to three decimal places."""

    scale = QUANTITY_SCALE


class Percent(ScaledDecimal):
    """Tax and markup rates stored as a fraction: 5% is ``Decimal("0.05")``."""

    scale = PERCENT_SCALE
