"""Assemble participant My Bookings browse cards from Booking rows."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.results import MemberBrowseBookingResult, MemberBrowseCardResult
from portal.domain.facility.constants import BookingType, MyBookingsCardKind, MyBookingsSection
from portal.domain.facility.my_bookings import classify_my_bookings_section


def project_my_bookings_cards(
    rows: list[MemberBrowseBookingResult], *, section: MyBookingsSection, user_id: UUID, now: datetime, facility_tz: ZoneInfo
) -> list[MemberBrowseCardResult]:
    """Group section-matching rows into one-time cards and Series projections."""
    matching = [
        row
        for row in rows
        if classify_my_bookings_section(
            status=row.status, end_at=row.end_at, payment_hold_expires_at=row.payment_hold_expires_at, now=now, facility_tz=facility_tz
        )
        == section
    ]
    series_occurrences: dict[UUID, list[MemberBrowseBookingResult]] = {}
    ungrouped: list[MemberBrowseBookingResult] = []
    for row in matching:
        if row.booking_type == BookingType.RECURRING.value and row.series_id is not None:
            series_occurrences.setdefault(row.series_id, []).append(row)
        else:
            ungrouped.append(row)

    cards: list[MemberBrowseCardResult] = [_one_time_card(row, user_id) for row in ungrouped]
    for series_id, occurrences in series_occurrences.items():
        ordered = sorted(occurrences, key=lambda item: (item.start_at, item.id))
        booker_id = ordered[0].user_id
        is_booker = booker_id == user_id
        cards.append(
            MemberBrowseCardResult(
                kind=MyBookingsCardKind.SERIES.value,
                is_booker=is_booker,
                is_view_only=not is_booker,
                series_id=series_id,
                series_title=ordered[0].series_title,
                occurrences=ordered,
            )
        )
    return sorted(cards, key=lambda card: _sort_key(card, section))


def paginate_my_bookings_cards(cards: list[MemberBrowseCardResult], page: int, page_size: int) -> tuple[list[MemberBrowseCardResult], int]:
    """Slice grouped cards into a stable page."""
    start = page * page_size
    return cards[start : start + page_size], len(cards)


def card_primary_facility_id(card: MemberBrowseCardResult) -> UUID | None:
    """Primary facility for a browse card image."""
    if card.kind == MyBookingsCardKind.SERIES.value and card.occurrences:
        return card.occurrences[0].facility_id
    if card.booking is not None:
        return card.booking.facility_id
    return None


def _one_time_card(row: MemberBrowseBookingResult, user_id: UUID) -> MemberBrowseCardResult:
    is_booker = row.user_id == user_id
    return MemberBrowseCardResult(kind=MyBookingsCardKind.ONE_TIME.value, is_booker=is_booker, is_view_only=not is_booker, booking=row)


def _sort_key(card: MemberBrowseCardResult, section: MyBookingsSection) -> tuple:
    times = _card_start_times(card)
    card_id = card.booking.id if card.booking is not None else card.series_id
    if section == MyBookingsSection.UPCOMING:
        return (min(times), str(card_id))
    return (-max(times).timestamp(), str(card_id))


def _card_start_times(card: MemberBrowseCardResult) -> list[datetime]:
    if card.kind == MyBookingsCardKind.SERIES.value:
        return [item.start_at for item in card.occurrences]
    if card.booking is not None:
        return [card.booking.start_at]
    return []
