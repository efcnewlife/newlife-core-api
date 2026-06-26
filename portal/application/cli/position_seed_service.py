"""
Position seed use case for CLI.
"""
import uuid
from typing import Any, Optional

import click

from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import OrgPosition, OrgPositionTranslation, SystemLocale


async def run_position_seed(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Seed org positions and translations. Idempotent on position code.
    """
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

    def _resolve_locale_id(locale_code: str) -> Optional[str]:
        normalized_target = _normalize_locale_code(locale_code)
        for locale_row in locale_rows or []:
            if normalized_target in _build_locale_variants(locale_row):
                return str(locale_row["id"])
        return None

    seeded = 0
    for row in rows:
        position_id = uuid.uuid4()
        await (
            session.insert(OrgPosition)
            .values(
                id=position_id,
                code=row["code"],
                can_own_ministry=row["can_own_ministry"],
                is_active=row.get("is_active", True),
                sequence=row.get("sequence"),
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_=dict(
                    can_own_ministry=row["can_own_ministry"],
                    is_active=row.get("is_active", True),
                    sequence=row.get("sequence"),
                ),
            )
            .execute()
        )
        existing_id = await (
            session.select(OrgPosition.id)
            .where(OrgPosition.code == row["code"])
            .fetchval()
        )
        position_id = existing_id or position_id

        row_team = row.get("team")
        row_office = row.get("office")
        for locale_code, translation in (row.get("translations") or {}).items():
            locale_id = _resolve_locale_id(locale_code)
            if not locale_id:
                click.echo(click.style(f"Skip translation: locale {locale_code} not found", fg="yellow"))
                continue
            team = row_team or translation.get("team")
            office = row_office or translation.get("office")
            await (
                session.insert(OrgPositionTranslation)
                .values(
                    id=uuid.uuid4(),
                    position_id=position_id,
                    locale_id=locale_id,
                    team=team,
                    office=office,
                    name=translation["name"],
                )
                .on_conflict_do_update(
                    index_elements=["position_id", "locale_id"],
                    set_=dict(
                        team=team,
                        office=office,
                        name=translation["name"],
                    ),
                )
                .execute()
            )
        seeded += 1

    await session.commit()
    click.echo(click.style(f"Seeded {seeded} positions", fg="green"))
    logger.info("Position seed completed: %s rows", seeded)
