"""
Shared org catalog seed helpers for CLI.
"""
import uuid
from typing import Any, Optional, Type

import click

from portal.libs.database import Session
from portal.models.system_locale import SystemLocale


async def run_catalog_seed(
    session: Session,
    rows: list[dict[str, Any]],
    *,
    catalog_model: Type,
    translation_model: Type,
    catalog_fk_field: str,
    label: str,
) -> None:
    """Upsert catalog rows and translations by stable code."""
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
        catalog_id = uuid.uuid4()
        await (
            session.insert(catalog_model)
            .values(
                id=catalog_id,
                code=row["code"],
                is_active=row.get("is_active", True),
                sequence=row.get("sequence"),
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_=dict(
                    is_active=row.get("is_active", True),
                    sequence=row.get("sequence"),
                ),
            )
            .execute()
        )
        existing_id = await (
            session.select(catalog_model.id)
            .where(catalog_model.code == row["code"])
            .fetchval()
        )
        catalog_id = existing_id or catalog_id

        for locale_code, translation in (row.get("translations") or {}).items():
            locale_id = _resolve_locale_id(locale_code)
            if not locale_id:
                click.echo(click.style(f"Skip translation: locale {locale_code} not found", fg="yellow"))
                continue
            await (
                session.insert(translation_model)
                .values(
                    id=uuid.uuid4(),
                    **{catalog_fk_field: catalog_id, "locale_id": locale_id, "name": translation["name"]},
                )
                .on_conflict_do_update(
                    index_elements=[catalog_fk_field, "locale_id"],
                    set_=dict(name=translation["name"]),
                )
                .execute()
            )
        seeded += 1

    await session.commit()
    click.echo(click.style(f"Seeded {seeded} {label}", fg="green"))
