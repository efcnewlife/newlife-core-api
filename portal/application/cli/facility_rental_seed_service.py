"""
Facility rental seed use case for CLI (rooms, templates, discounts, surcharges, policy).

Seed creates rate templates only; rooms are not bound to rates (pricing falls back to active templates).
"""
import json
import uuid
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import click
from pydantic import ValidationError

from portal.domain.facility.rate_applicability import parse_applicability
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import (
    FacilityBooking,
    FacilityBookingOverrideLog,
    FacilityBookingRoom,
    FacilityBookingSlot,
    FacilityBookingSurcharge,
    FacilityRentalDiscountRule,
    FacilityRentalPolicySetting,
    FacilityRentalRate,
    FacilityRentalRateTemplate,
    FacilityRentalSurcharge,
    FacilityRoom,
    FacilityRoomSlotTemplate,
    FacilityRoomBlackout,
    FacilityRoomTranslation,
    SystemLocale,
)


async def clear_facility_rental_catalog(session: Session) -> None:
    """
    Hard-delete facility booking and rental catalog rows so seed can recreate rooms by code.
    Order respects FK constraints (NO ACTION on booking -> room/surcharge).
    """
    await session.delete(FacilityBookingSurcharge).execute()
    await session.delete(FacilityBookingOverrideLog).execute()
    await session.delete(FacilityBookingSlot).execute()
    await session.delete(FacilityBookingRoom).execute()
    await session.delete(FacilityBooking).execute()
    await session.delete(FacilityRoomBlackout).execute()
    await session.delete(FacilityRoomSlotTemplate).execute()
    await session.delete(FacilityRentalPolicySetting).execute()
    await session.delete(FacilityRentalRate).execute()
    await session.delete(FacilityRentalRateTemplate).execute()
    await session.delete(FacilityRentalDiscountRule).execute()
    await session.delete(FacilityRentalSurcharge).execute()
    await session.delete(FacilityRoomTranslation).execute()
    await session.delete(FacilityRoom).execute()


def _normalize_locale_code(locale_code: str) -> str:
    return locale_code.strip().replace("_", "-").lower()


def _build_locale_variants(locale_row: dict[str, Any]) -> set[str]:
    language_code = (locale_row.get("language_code") or "").strip()
    script_code = (locale_row.get("script_code") or "").strip()
    region_code = (locale_row.get("region_code") or "").strip()
    variants: set[str] = set()
    if language_code:
        variants.add(_normalize_locale_code(language_code))
    if language_code and region_code:
        variants.add(_normalize_locale_code(f"{language_code}-{region_code}"))
    if language_code and script_code and region_code:
        variants.add(_normalize_locale_code(f"{language_code}-{script_code}-{region_code}"))
    return variants


def _resolve_locale_id(locale_rows: list[dict[str, Any]], locale_code: str) -> Optional[str]:
    normalized_target = _normalize_locale_code(locale_code)
    for locale_row in locale_rows or []:
        if normalized_target in _build_locale_variants(locale_row):
            return str(locale_row["id"])
    return None


async def _upsert_translations(
    session: Session,
    *,
    locale_rows: list[dict[str, Any]],
    translations: dict[str, dict[str, str]],
    translation_model: type,
    fk_field: str,
    fk_value: UUID,
) -> None:
    for locale_code, translation in (translations or {}).items():
        locale_id = _resolve_locale_id(locale_rows, locale_code)
        if not locale_id:
            click.echo(click.style(f"Skip translation: locale {locale_code} not found", fg="yellow"))
            continue
        await (
            session.insert(translation_model)
            .values(
                id=uuid.uuid4(),
                **{fk_field: fk_value, "locale_id": locale_id, "name": translation["name"]},
            )
            .on_conflict_do_update(
                index_elements=[fk_field, "locale_id"],
                set_=dict(name=translation["name"]),
            )
            .execute()
        )


async def _upsert_room(
    session: Session,
    row: dict[str, Any],
    locale_rows: list[dict[str, Any]],
) -> UUID:
    room_id = uuid.uuid4()
    await (
        session.insert(FacilityRoom)
        .values(
            id=room_id,
            code=row["code"],
            room_number=row.get("room_number"),
            capacity=row.get("capacity"),
            is_active=row.get("is_active", True),
            sequence=row.get("sequence"),
        )
        .on_conflict_do_update(
            index_elements=["code"],
            set_=dict(
                room_number=row.get("room_number"),
                capacity=row.get("capacity"),
                is_active=row.get("is_active", True),
                sequence=row.get("sequence"),
            ),
        )
        .execute()
    )
    existing_id = await (
        session.select(FacilityRoom.id)
        .where(FacilityRoom.code == row["code"])
        .fetchval()
    )
    room_id = existing_id or room_id
    await _upsert_translations(
        session,
        locale_rows=locale_rows,
        translations=row.get("translations") or {},
        translation_model=FacilityRoomTranslation,
        fk_field="room_id",
        fk_value=room_id,
    )
    return room_id


async def _upsert_template(session: Session, row: dict[str, Any]) -> UUID:
    try:
        validated_applicability = parse_applicability(row.get("applicability"))
    except (ValidationError, ValueError) as error:
        raise click.ClickException(
            f"Invalid applicability for template {row.get('name')}: {error}"
        ) from error

    applicability_bind = (
        json.dumps(validated_applicability) if validated_applicability is not None else None
    )
    template_id = uuid.uuid4()
    unit_amount = row.get("unit_amount") if row.get("unit_amount") is not None else Decimal("30.00")
    currency = row.get("currency") or "CAD"
    await (
        session.insert(FacilityRentalRateTemplate)
        .values(
            id=template_id,
            name=row["name"],
            billing_unit=row["billing_unit"],
            applicability=applicability_bind,
            unit_amount=unit_amount,
            currency=currency,
            is_default=row.get("is_default", False),
            is_active=row.get("is_active", True),
        )
        .on_conflict_do_update(
            index_elements=["name"],
            set_=dict(
                billing_unit=row["billing_unit"],
                applicability=applicability_bind,
                unit_amount=unit_amount,
                currency=currency,
                is_default=row.get("is_default", False),
                is_active=row.get("is_active", True),
                is_deleted=False,
                delete_reason=None,
            ),
        )
        .execute()
    )
    existing_id = await (
        session.select(FacilityRentalRateTemplate.id)
        .where(FacilityRentalRateTemplate.name == row["name"])
        .where(FacilityRentalRateTemplate.is_deleted == False)
        .fetchval()
    )
    return existing_id or template_id


async def _upsert_discount(session: Session, row: dict[str, Any]) -> None:
    await (
        session.insert(FacilityRentalDiscountRule)
        .values(
            id=uuid.uuid4(),
            code=row["code"],
            percent_off=row["percent_off"],
            is_active=row.get("is_active", True),
            description=row.get("description"),
        )
        .on_conflict_do_update(
            index_elements=["code"],
            set_=dict(
                percent_off=row["percent_off"],
                is_active=row.get("is_active", True),
                description=row.get("description"),
            ),
        )
        .execute()
    )


async def _upsert_surcharge(session: Session, row: dict[str, Any]) -> None:
    await (
        session.insert(FacilityRentalSurcharge)
        .values(
            id=uuid.uuid4(),
            code=row["code"],
            charge_type=row["charge_type"],
            unit_amount=row["unit_amount"],
            currency=row.get("currency", "CAD"),
            is_active=row.get("is_active", True),
            applies_to_booking_type=row.get("applies_to_booking_type"),
            remark=row.get("remark"),
        )
        .on_conflict_do_update(
            index_elements=["code"],
            set_=dict(
                charge_type=row["charge_type"],
                unit_amount=row["unit_amount"],
                currency=row.get("currency", "CAD"),
                is_active=row.get("is_active", True),
                applies_to_booking_type=row.get("applies_to_booking_type"),
                remark=row.get("remark"),
            ),
        )
        .execute()
    )


async def _upsert_policy_setting(
    session: Session,
    row: dict[str, Any],
    room_ids_by_code: dict[str, UUID],
) -> None:
    facility_code = row.get("facility_code")
    facility_id: Optional[UUID] = None
    if facility_code:
        facility_id = room_ids_by_code.get(facility_code)
        if not facility_id:
            click.echo(
                click.style(
                    f"Skip policy {row['setting_key']}: room code {facility_code} not found",
                    fg="yellow",
                )
            )
            return

    query = (
        session.select(FacilityRentalPolicySetting.id)
        .where(FacilityRentalPolicySetting.setting_key == row["setting_key"])
        .where(FacilityRentalPolicySetting.is_deleted == False)
    )
    if facility_id is None:
        query = query.where(FacilityRentalPolicySetting.facility_id.is_(None))
    else:
        query = query.where(FacilityRentalPolicySetting.facility_id == facility_id)
    existing_id = await query.fetchval()

    values = dict(
        amount=row["amount"],
        currency=row.get("currency", "CAD"),
        is_active=row.get("is_active", True),
    )
    if existing_id:
        await (
            session.update(FacilityRentalPolicySetting)
            .values(**values)
            .where(FacilityRentalPolicySetting.id == existing_id)
            .execute()
        )
        return

    await (
        session.insert(FacilityRentalPolicySetting)
        .values(
            id=uuid.uuid4(),
            setting_key=row["setting_key"],
            facility_id=facility_id,
            **values,
        )
        .execute()
    )


async def run_facility_rental_seed(
    session: Session,
    *,
    room_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    discount_rows: list[dict[str, Any]],
    surcharge_rows: list[dict[str, Any]],
    policy_rows: list[dict[str, Any]],
    global_rate_unit_amount: Decimal,
    reset: bool = False,
) -> None:
    """Upsert facility rooms, templates, rate bindings, discounts, surcharges, and policy settings."""
    _ = global_rate_unit_amount
    if reset:
        click.echo(click.style("Clearing facility booking and rental catalog data...", fg="yellow"))
        await clear_facility_rental_catalog(session)
        await session.commit()
        click.echo(click.style("Cleared.", fg="yellow"))

    locale_rows = await (
        session.select(
            SystemLocale.id,
            SystemLocale.language_code,
            SystemLocale.region_code,
            SystemLocale.script_code,
        )
        .where(SystemLocale.is_active == True)
        .where(SystemLocale.is_deleted == False)
        .fetch()
    )

    billing_units_seen: set[str] = set()
    templates_seeded = 0
    for row in template_rows:
        await _upsert_template(session, row)
        billing_units_seen.add(row["billing_unit"])
        templates_seeded += 1

    if "hourly" not in billing_units_seen or "daily_flat" not in billing_units_seen:
        raise click.ClickException("Seed requires hourly and daily_flat rental rate templates")

    room_ids_by_code: dict[str, UUID] = {}
    rooms_seeded = 0

    for row in room_rows:
        room_id = await _upsert_room(session, row, locale_rows)
        room_ids_by_code[row["code"]] = room_id
        rooms_seeded += 1

    for row in discount_rows:
        await _upsert_discount(session, row)
    for row in surcharge_rows:
        await _upsert_surcharge(session, row)
    for row in policy_rows:
        await _upsert_policy_setting(session, row, room_ids_by_code)

    await session.commit()
    click.echo(
        click.style(
            f"Seeded {templates_seeded} templates, {rooms_seeded} rooms "
            f"(no room rate bindings; pricing uses active templates), "
            f"{len(discount_rows)} discounts, {len(surcharge_rows)} surcharges, "
            f"{len(policy_rows)} policy settings",
            fg="green",
        )
    )
    logger.info(
        "Facility rental seed completed: templates=%s rooms=%s discounts=%s surcharges=%s policy=%s",
        templates_seeded,
        rooms_seeded,
        len(discount_rows),
        len(surcharge_rows),
        len(policy_rows),
    )
