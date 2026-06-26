"""
Room slot template overlap static method tests.
"""
from datetime import date, time

from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import (
    RoomSlotTemplateRepository,
)


def test_effective_dates_overlap_false_when_ranges_disjoint():
    assert RoomSlotTemplateRepository.effective_dates_overlap(
        date(2026, 6, 1),
        date(2026, 6, 30),
        date(2026, 7, 1),
        date(2026, 7, 31),
    ) is False


def test_effective_dates_overlap_true_when_open_ended():
    assert RoomSlotTemplateRepository.effective_dates_overlap(
        date(2026, 6, 1),
        None,
        None,
        date(2026, 12, 31),
    ) is True


def test_time_ranges_overlap_true_for_intersection():
    assert RoomSlotTemplateRepository.time_ranges_overlap(
        time(9, 0),
        time(12, 0),
        time(11, 0),
        time(13, 0),
    ) is True


def test_time_ranges_overlap_false_at_boundary():
    assert RoomSlotTemplateRepository.time_ranges_overlap(
        time(9, 0),
        time(10, 0),
        time(10, 0),
        time(11, 0),
    ) is False
