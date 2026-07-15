"""
Shared translation query helpers for org repositories.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from portal.models import OrgMinistryTranslation, OrgPositionTranslation, SystemLocale


def locale_scoped_max(column, translation_model, locale_id: Optional[UUID]):
    if locale_id:
        return sa.func.max(
            sa.case(
                (translation_model.locale_id == locale_id, column),
                else_=None,
            )
        )
    return sa.func.max(column)


def ministry_translations_agg():
    translation_json = sa.cast(
        sa.func.json_build_object(
            sa.cast("locale_id", sa.VARCHAR(16)), OrgMinistryTranslation.locale_id,
            sa.cast("name", sa.VARCHAR(8)), OrgMinistryTranslation.name,
            sa.cast("description", sa.VARCHAR(16)), OrgMinistryTranslation.description,
            sa.cast("remark", sa.VARCHAR(8)), OrgMinistryTranslation.remark,
            sa.cast("schedule_note", sa.VARCHAR(16)), OrgMinistryTranslation.schedule_note,
        ),
        JSONB,
    )
    return sa.func.coalesce(
        sa.func.array_agg(sa.distinct(translation_json)).filter(OrgMinistryTranslation.id.isnot(None)),
        sa.cast(sa.text("'{}'"), sa.ARRAY(JSONB)),
    ).label("translations")


def position_translations_agg():
    translation_json = sa.cast(
        sa.func.json_build_object(
            sa.cast("locale_id", sa.VARCHAR(16)), OrgPositionTranslation.locale_id,
            sa.cast("name", sa.VARCHAR(8)), OrgPositionTranslation.name,
            sa.cast("description", sa.VARCHAR(16)), OrgPositionTranslation.description,
            sa.cast("remark", sa.VARCHAR(8)), OrgPositionTranslation.remark,
        ),
        JSONB,
    )
    return sa.func.coalesce(
        sa.func.array_agg(sa.distinct(translation_json)).filter(OrgPositionTranslation.id.isnot(None)),
        sa.cast(sa.text("'{}'"), sa.ARRAY(JSONB)),
    ).label("translations")


def default_locale_subquery():
    return (
        sa.select(SystemLocale.id)
        .where(SystemLocale.is_default == True)
        .where(SystemLocale.is_deleted == False)
        .limit(1)
        .scalar_subquery()
    )


def ministry_name_fallback(locale_id: Optional[UUID]):
    """Coalesce resolved locale, default locale, then any translation name."""
    resolved_name = None
    if locale_id:
        resolved_name = sa.func.max(
            sa.case(
                (OrgMinistryTranslation.locale_id == locale_id, OrgMinistryTranslation.name),
                else_=None,
            )
        )
    default_locale_name = sa.func.max(
        sa.case(
            (OrgMinistryTranslation.locale_id == default_locale_subquery(), OrgMinistryTranslation.name),
            else_=None,
        )
    )
    any_name = sa.func.max(OrgMinistryTranslation.name)
    if resolved_name is not None:
        return sa.func.coalesce(resolved_name, default_locale_name, any_name)
    return sa.func.coalesce(default_locale_name, any_name)


def position_name_fallback(locale_id: Optional[UUID]):
    """Coalesce resolved locale, default locale, then any translation name."""
    resolved_name = None
    if locale_id:
        resolved_name = sa.func.max(
            sa.case(
                (OrgPositionTranslation.locale_id == locale_id, OrgPositionTranslation.name),
                else_=None,
            )
        )
    default_locale_name = sa.func.max(
        sa.case(
            (OrgPositionTranslation.locale_id == default_locale_subquery(), OrgPositionTranslation.name),
            else_=None,
        )
    )
    any_name = sa.func.max(OrgPositionTranslation.name)
    if resolved_name is not None:
        return sa.func.coalesce(resolved_name, default_locale_name, any_name)
    return sa.func.coalesce(default_locale_name, any_name)


