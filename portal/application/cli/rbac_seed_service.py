"""
RBAC seed use case for CLI.
"""
import time
from typing import Any, Optional

import click

from portal.libs.database import Session
from portal.libs.consts.enums import ResourceType
from portal.libs.logger import logger
from portal.models import (
    SystemLocale,
    AuthRole,
    AuthRoleTranslation,
    AuthResource,
    AuthResourceTranslation,
    AuthVerb,
    AuthVerbTranslation,
    AuthPermission,
    AuthPermissionTranslation,
    AuthRolePermission,
)
from portal.cli.datas.rbac_seed_data import (
    SUPPORTED_LOCALES,
    seed_verbs,
    parent_resources,
    resources,
)


async def run_rbac_seed(session: Session):
    """
    Seed verbs, resources, permissions, roles, and role-permission mappings.
    Idempotent: uses ON CONFLICT DO NOTHING on unique keys.
    :param session:
    :return:
    """

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

    def _resolve_locale_id(locale_rows: list[dict[str, Any]], target_locale: str) -> Optional[str]:
        normalized_target = _normalize_locale_code(target_locale)
        for locale_row in locale_rows:
            if normalized_target in _build_locale_variants(locale_row):
                return str(locale_row["id"])
        return None

    def _locale_text(
        entry: dict[str, Any],
        locale_code: str,
        fallback_field: str,
        translation_key: str = "translations",
    ) -> str:
        translations = entry.get(translation_key) or {}
        fallback_value = entry.get(fallback_field) or ""
        return translations.get(locale_code) or translations.get("en") or fallback_value

    sequence_base = time.time()
    sequence_counter = 0

    def _build_resource_sequence(raw_sequence: Any) -> float:
        nonlocal sequence_counter
        sequence_counter += 1
        if isinstance(raw_sequence, int):
            return sequence_base + (raw_sequence / 1000) + (sequence_counter / 1_000_000)
        if isinstance(raw_sequence, float):
            return raw_sequence
        return sequence_base + (sequence_counter / 1_000_000)

    try:
        # Load seed data from portal.cli.datas.rbac_seed_data

        # 1) Seed verbs
        verbs = seed_verbs
        for v in verbs:
            await (
                session
                .insert(AuthVerb)
                .values(action=v["action"], is_active=True)
                .on_conflict_do_update(
                    index_elements=["action"],
                    set_=dict(is_active=True),
                )
                .execute()
            )

        # 2) Seed parent resources for grouping
        # parent_resources imported
        for pr in parent_resources:
            parent_sequence = _build_resource_sequence(pr.get("sequence"))
            await (
                session
                .insert(AuthResource)
                .values(
                    id=pr.get("id"),
                    code=pr["code"],
                    key=pr.get("key", pr["code"]).upper(),
                    icon=pr.get("icon"),
                    path=pr.get("path"),
                    sequence=parent_sequence,
                    type=pr.get("type", ResourceType.GENERAL.value),
                    is_visible=True,
                )
                .on_conflict_do_update(
                    index_elements=["code"],
                    set_=dict(
                        key=pr.get("key", pr["code"]).upper(),
                        icon=pr.get("icon"),
                        path=pr.get("path"),
                        pid=pr.get("pid"),
                        sequence=parent_sequence,
                        type=pr.get("type", ResourceType.GENERAL.value),
                        is_visible=True,
                    )
                )
                .execute()
            )

        # resources imported
        for r in resources:
            resource_type_value = r.get("type", ResourceType.GENERAL.value)
            resource_sequence = _build_resource_sequence(r.get("sequence"))
            await (
                session
                .insert(AuthResource)
                .values(
                    code=r["code"],
                    key=r.get("key", r["code"]),
                    icon=r.get("icon"),
                    path=r.get("path"),
                    pid=r.get("pid"),
                    sequence=resource_sequence,
                    type=resource_type_value,
                    is_visible=True,
                )
                .on_conflict_do_update(
                    index_elements=["code"],
                    set_=dict(
                        key=r.get("key", r["code"]),
                        icon=r.get("icon"),
                        path=r.get("path"),
                        pid=r.get("pid"),
                        sequence=resource_sequence,
                        type=resource_type_value,
                        is_visible=True,
                    )
                )
                .execute()
            )

        # 4) Fetch current verbs/resources for id mapping
        locale_rows = await (
            session
            .select(SystemLocale.id, SystemLocale.language_code, SystemLocale.script_code, SystemLocale.region_code)
            .where(SystemLocale.is_deleted == False)
            .where(SystemLocale.is_active == True)
            .fetch()
        )
        locale_id_map = {
            locale_code: _resolve_locale_id(locale_rows=locale_rows, target_locale=locale_code)
            for locale_code in SUPPORTED_LOCALES
        }
        missing_locales = [locale_code for locale_code, locale_id in locale_id_map.items() if not locale_id]
        if missing_locales:
            raise ValueError(
                "Missing locales required by RBAC seed: "
                f"{', '.join(missing_locales)}. Run `init-locales` first."
            )

        verb_rows = await session.select(AuthVerb).fetch()
        resource_rows = await session.select(AuthResource).fetch()
        action_to_verb_id = {row["action"]: row["id"] for row in verb_rows}
        resource_code_to = {row["code"]: row for row in resource_rows}

        # 4.1) Seed verb translations
        for v in verbs:
            verb_id = action_to_verb_id.get(v["action"])
            if not verb_id:
                continue
            for locale_code in SUPPORTED_LOCALES:
                locale_id = locale_id_map.get(locale_code)
                if not locale_id:
                    continue
                localized_name = _locale_text(entry=v, locale_code=locale_code, fallback_field="display_name")
                await (
                    session
                    .insert(AuthVerbTranslation)
                    .values(verb_id=verb_id, locale_id=locale_id, name=localized_name)
                    .on_conflict_do_update(
                        index_elements=["verb_id", "locale_id"],
                        set_=dict(name=localized_name),
                    )
                    .execute()
                )

        # 4.2) Seed resource translations
        all_resources = parent_resources + resources
        seed_resource_map = {item["code"]: item for item in all_resources}
        for resource_code, resource_row in resource_code_to.items():
            seed_item = seed_resource_map.get(resource_code)
            if not seed_item:
                continue
            for locale_code in SUPPORTED_LOCALES:
                locale_id = locale_id_map.get(locale_code)
                if not locale_id:
                    continue
                localized_name = _locale_text(entry=seed_item, locale_code=locale_code, fallback_field="name")
                localized_description = _locale_text(
                    entry=seed_item,
                    locale_code=locale_code,
                    fallback_field="description",
                    translation_key="description_translations",
                )
                await (
                    session
                    .insert(AuthResourceTranslation)
                    .values(
                        resource_id=resource_row["id"],
                        locale_id=locale_id,
                        name=localized_name,
                        description=localized_description,
                    )
                    .on_conflict_do_update(
                        index_elements=["resource_id", "locale_id"],
                        set_=dict(name=localized_name, description=localized_description),
                    )
                    .execute()
                )

        # 5) Seed permissions: resource x verb (skip parent-only resources)
        for res_code, res in resource_code_to.items():
            if ":" not in res_code:
                continue
            for action, verb_id in action_to_verb_id.items():
                code = f"{res_code}:{action}"
                await (
                    session
                    .insert(AuthPermission)
                    .values(
                        code=code,
                        resource_id=res["id"],
                        verb_id=verb_id,
                        is_active=True,
                    )
                    .on_conflict_do_update(
                        index_elements=["code"],
                        set_=dict(
                            is_active=True,
                        )
                    )
                    .execute()
                )

        # 6) Roles: keep only one role `admin`
        # Delete all roles (cascades will clean associations)
        await (
            session
            .delete(AuthRole)
            .execute()
        )
        # Insert fresh `admin` role
        await (
            session
            .insert(AuthRole)
            .values(code='admin', is_active=True)
            .execute()
        )

        # Permissions lookup
        perm_rows = await session.select(AuthPermission).fetch()
        code_to_perm = {row["code"]: row for row in perm_rows}

        # 6.1) Seed permission translations
        action_seed_map = {item["action"]: item for item in verbs}
        for permission_code, permission_row in code_to_perm.items():
            split_code = permission_code.rsplit(":", 1)
            if len(split_code) != 2:
                continue
            resource_code, action = split_code
            seed_resource = seed_resource_map.get(resource_code, {})
            seed_verb = action_seed_map.get(action, {})
            for locale_code in SUPPORTED_LOCALES:
                locale_id = locale_id_map.get(locale_code)
                if not locale_id:
                    continue
                resource_name = _locale_text(entry=seed_resource, locale_code=locale_code, fallback_field="name")
                verb_name = _locale_text(entry=seed_verb, locale_code=locale_code, fallback_field="display_name")
                localized_permission_name = f"{resource_name} {verb_name}".strip()
                resource_description = _locale_text(
                    entry=seed_resource,
                    locale_code=locale_code,
                    fallback_field="description",
                    translation_key="description_translations",
                )
                localized_permission_description = (
                    f"{resource_description} ({verb_name})".strip()
                    if resource_description
                    else f"Permission for {permission_code}"
                )
                await (
                    session
                    .insert(AuthPermissionTranslation)
                    .values(
                        permission_id=permission_row["id"],
                        locale_id=locale_id,
                        name=localized_permission_name,
                        description=localized_permission_description,
                    )
                    .on_conflict_do_update(
                        index_elements=["permission_id", "locale_id"],
                        set_=dict(
                            name=localized_permission_name,
                            description=localized_permission_description,
                        ),
                    )
                    .execute()
                )

        # 7) Grant permissions to `admin`: all except resource:* and verb:*
        excluded_prefixes = ("system:resource:", "system:verb:", "system:fcm_device:", "comms:notification")

        # Fetch admin role id
        admin_row = await (
            session
            .select(AuthRole)
            .where(AuthRole.code == 'admin')
            .fetchrow()
        )
        if admin_row:
            role_name_map = {
                "zh-TW": "系統管理員",
                "zh-CN": "系统管理员",
                "en": "Administrator",
            }
            for locale_code in SUPPORTED_LOCALES:
                locale_id = locale_id_map.get(locale_code)
                if not locale_id:
                    continue
                role_name = role_name_map.get(locale_code) or role_name_map["en"]
                await (
                    session
                    .insert(AuthRoleTranslation)
                    .values(role_id=admin_row["id"], locale_id=locale_id, name=role_name)
                    .on_conflict_do_update(
                        index_elements=["role_id", "locale_id"],
                        set_=dict(name=role_name),
                    )
                    .execute()
                )

        inserted_count = 0
        if admin_row:
            for p_code, perm_row in code_to_perm.items():
                if p_code.startswith(excluded_prefixes):
                    continue
                await (
                    session
                    .insert(AuthRolePermission)
                    .values(role_id=admin_row["id"], permission_id=perm_row["id"])
                    .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
                    .execute()
                )
                inserted_count += 1

        await session.commit()
        click.echo(click.style("RBAC initialized successfully.", fg="bright_green"))
        logger.info(f"RBAC init completed. role-permissions inserted/ensured: {inserted_count}")
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"RBAC init failed: {e}", fg="red"))
        logger.exception(e)
        raise
