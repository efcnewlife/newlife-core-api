"""Managed Booking Discount percentage rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator

DISCOUNT_PERCENT_MIN = Decimal("0")
DISCOUNT_PERCENT_MAX = Decimal("100")
DISCOUNT_PERCENT_MAX_DECIMAL_PLACES = 2


class InvalidDiscountPercent(ValueError):
    """Raised when a managed Discount Rule percentage is outside catalog bounds."""


def normalize_discount_percent(value: Decimal) -> Decimal:
    """Accept 0-100 inclusive with at most two decimal places."""
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    if amount < DISCOUNT_PERCENT_MIN or amount > DISCOUNT_PERCENT_MAX:
        raise InvalidDiscountPercent("Discount percent must be between 0 and 100")
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -DISCOUNT_PERCENT_MAX_DECIMAL_PLACES:
        raise InvalidDiscountPercent("Discount percent may have at most two decimal places")
    return amount


DiscountPercent = Annotated[Decimal, AfterValidator(normalize_discount_percent)]
