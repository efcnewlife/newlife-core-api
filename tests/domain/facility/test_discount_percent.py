"""Discount percent catalog rules."""

from decimal import Decimal

import pytest

from portal.domain.facility.discount_percent import InvalidDiscountPercent, normalize_discount_percent


def test_normalize_discount_percent_accepts_zero_and_one_hundred():
    assert normalize_discount_percent(Decimal("0")) == Decimal("0")
    assert normalize_discount_percent(Decimal("100.00")) == Decimal("100.00")


def test_normalize_discount_percent_accepts_two_decimal_places():
    assert normalize_discount_percent(Decimal("30.25")) == Decimal("30.25")


def test_normalize_discount_percent_rejects_out_of_range():
    with pytest.raises(InvalidDiscountPercent, match="0 and 100"):
        normalize_discount_percent(Decimal("-0.01"))
    with pytest.raises(InvalidDiscountPercent, match="0 and 100"):
        normalize_discount_percent(Decimal("100.01"))


def test_normalize_discount_percent_rejects_more_than_two_decimal_places():
    with pytest.raises(InvalidDiscountPercent, match="two decimal"):
        normalize_discount_percent(Decimal("30.001"))
