"""
Days-of-week bitmask unit tests.
"""
import pytest

from portal.domain.facility.days_of_week_mask import (
    day_to_bit,
    days_to_mask,
    mask_to_days,
    masks_share_day,
)


def test_day_to_bit():
    assert day_to_bit(0) == 1
    assert day_to_bit(6) == 64


def test_day_to_bit_invalid():
    with pytest.raises(ValueError):
        day_to_bit(-1)
    with pytest.raises(ValueError):
        day_to_bit(7)


def test_days_to_mask_weekdays():
    assert days_to_mask([0, 1, 2, 3, 4]) == 31


def test_days_to_mask_dedupes():
    assert days_to_mask([0, 0, 1]) == 3


def test_days_to_mask_empty():
    with pytest.raises(ValueError):
        days_to_mask([])


def test_mask_to_days():
    assert mask_to_days(31) == [0, 1, 2, 3, 4]
    assert mask_to_days(127) == [0, 1, 2, 3, 4, 5, 6]


def test_mask_to_days_invalid():
    with pytest.raises(ValueError):
        mask_to_days(0)
    with pytest.raises(ValueError):
        mask_to_days(256)


def test_masks_share_day():
    assert masks_share_day(1, 2) is False
    assert masks_share_day(3, 2) is True
