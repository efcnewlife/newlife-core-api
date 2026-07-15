"""
Microsoft Graph user directory sync use case for CLI.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import click

from portal.application.auth.microsoft_profile_mapper import profile_fields_from_graph_user
from portal.application.cli.microsoft_user_sync_filters import classify_service_account
from portal.config import settings
from portal.domain.auth.ports import UserRepositoryPort
from portal.domain.member.constants import AccountKind
from portal.libs.consts.enums import ThirdPartyProvider
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace
from portal.providers.microsoft_graph_provider import GraphUserRecord, MicrosoftGraphProvider

SYNC_EMAIL_DOMAIN = "efcnewlife.org"
DEFAULT_SYNC_FILTER = (
    "userType eq 'Member' and accountEnabled eq true "
    f"and endsWith(userPrincipalName,'@{SYNC_EMAIL_DOMAIN}') "
    "and givenName ne null and surname ne null"
)
DRY_RUN_OUTPUT_ROOT = Path("temp") / "microsoft_user_sync"


@dataclass
class MicrosoftUserSyncStats:
    """Counters for sync run output."""

    created: int = 0
    updated: int = 0
    linked: int = 0
    skipped_no_email: int = 0
    skipped_domain_mismatch: int = 0
    skipped_not_real_person: int = 0
    skipped_service_account: int = 0
    total_fetched: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run_output_dir: Optional[str] = None
    dry_run_actions: list[dict[str, Any]] = field(default_factory=list)


def resolve_sync_email(record: GraphUserRecord) -> Optional[str]:
    raw = (record.email or record.user_principal_name or "").strip().lower()
    return raw or None


def is_sync_email_domain(email: str, domain: str = SYNC_EMAIL_DOMAIN) -> bool:
    normalized = email.strip().lower()
    return normalized.endswith(f"@{domain}")


def is_real_person(record: GraphUserRecord) -> bool:
    """Require both givenName and surname to treat the Graph user as a person."""
    given_name = (record.given_name or "").strip()
    surname = (record.surname or "").strip()
    return bool(given_name and surname)


def is_syncable_directory_user(record: GraphUserRecord, email: str) -> Optional[str]:
    """
    Return skip reason when the user should not be synced, or None when syncable.
    """
    if not is_real_person(record):
        return "missing_given_name_or_surname"
    service_reason = classify_service_account(record, email)
    if service_reason:
        return service_reason
    return None


def default_dry_run_output_dir() -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DRY_RUN_OUTPUT_ROOT / run_id


def graph_user_to_dict(record: GraphUserRecord) -> dict[str, Any]:
    return {
        "object_id": record.object_id,
        "email": record.email,
        "given_name": record.given_name,
        "surname": record.surname,
        "display_name": record.display_name,
        "account_enabled": record.account_enabled,
        "user_principal_name": record.user_principal_name,
        "user_type": record.user_type,
    }


def write_dry_run_output(
    stats: MicrosoftUserSyncStats,
    *,
    output_dir: Path,
    filter_expr: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "dry_run": True,
        "filter": filter_expr,
        "fetched": stats.total_fetched,
        "created": stats.created,
        "updated": stats.updated,
        "linked": stats.linked,
        "skipped_no_email": stats.skipped_no_email,
        "skipped_domain_mismatch": stats.skipped_domain_mismatch,
        "skipped_not_real_person": stats.skipped_not_real_person,
        "skipped_service_account": stats.skipped_service_account,
        "errors": stats.errors,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "actions.json").write_text(
        json.dumps(stats.dry_run_actions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_dir


class MicrosoftUserSyncService:
    """Sync Entra users into auth tables."""

    def __init__(
        self,
        session: Session,
        user_repository: UserRepositoryPort,
        graph_provider: MicrosoftGraphProvider,
    ):
        self._session = session
        self._repository = user_repository
        self._graph_provider = graph_provider

    @distributed_trace()
    async def run(
        self,
        *,
        dry_run: bool = False,
        filter_expr: Optional[str] = None,
        dry_run_output_dir: Optional[Path] = None,
    ) -> MicrosoftUserSyncStats:
        if not self._graph_provider.is_configured():
            raise RuntimeError(
                "Microsoft Graph is not configured. Set AZURE_TENANT_ID, "
                "AZURE_APP_CLIENT_ID, and AZURE_APP_CLIENT_SECRET."
            )
        if not settings.AZURE_TENANT_ID:
            raise RuntimeError("AZURE_TENANT_ID is required for directory sync")

        tenant_id = UUID(str(settings.AZURE_TENANT_ID).strip())
        odata_filter = filter_expr or DEFAULT_SYNC_FILTER
        stats = MicrosoftUserSyncStats()

        async for record in self._graph_provider.list_users(filter_expr=odata_filter):
            stats.total_fetched += 1
            try:
                await self._sync_one(
                    record=record,
                    tenant_id=tenant_id,
                    dry_run=dry_run,
                    stats=stats,
                )
            except Exception as error:
                message = f"Failed to sync user {record.object_id}: {error}"
                logger.exception(message)
                stats.errors.append(message)

        if dry_run:
            await self._session.rollback()
            output_dir = dry_run_output_dir or default_dry_run_output_dir()
            write_dry_run_output(
                stats,
                output_dir=output_dir,
                filter_expr=odata_filter,
            )
            stats.dry_run_output_dir = str(output_dir.resolve())
        else:
            await self._session.commit()

        return stats

    def _append_dry_run_action(
        self,
        stats: MicrosoftUserSyncStats,
        action: str,
        record: GraphUserRecord,
        *,
        email: Optional[str] = None,
        user_id: Optional[UUID] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        preferred_name: Optional[str] = None,
        skip_reason: Optional[str] = None,
    ) -> None:
        payload: dict[str, Any] = {
            "action": action,
            "graph_user": graph_user_to_dict(record),
        }
        if skip_reason:
            payload["skip_reason"] = skip_reason
        if email is not None:
            payload["email"] = email
        if user_id is not None:
            payload["user_id"] = str(user_id)
        if action == "create":
            payload["auth_user"] = {
                "verified": True,
                "is_active": record.account_enabled,
                "is_admin": False,
                "account_kind": AccountKind.MEMBER.value,
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": preferred_name,
            }
        if action in ("update", "link"):
            payload["profile"] = {
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": preferred_name,
                "is_active": record.account_enabled,
            }
        stats.dry_run_actions.append(payload)

    async def _sync_one(
        self,
        *,
        record: GraphUserRecord,
        tenant_id: UUID,
        dry_run: bool,
        stats: MicrosoftUserSyncStats,
    ) -> None:
        email = resolve_sync_email(record)
        if not email:
            stats.skipped_no_email += 1
            if dry_run:
                self._append_dry_run_action(stats, "skip_no_email", record)
            return
        if not is_sync_email_domain(email):
            stats.skipped_domain_mismatch += 1
            if dry_run:
                self._append_dry_run_action(stats, "skip_domain_mismatch", record, email=email)
            return

        skip_reason = is_syncable_directory_user(record, email)
        if skip_reason:
            if skip_reason == "missing_given_name_or_surname":
                stats.skipped_not_real_person += 1
                action = "skip_not_real_person"
            else:
                stats.skipped_service_account += 1
                action = "skip_service_account"
            if dry_run:
                self._append_dry_run_action(
                    stats,
                    action,
                    record,
                    email=email,
                    skip_reason=skip_reason,
                )
            return

        first_name, last_name, preferred_name = profile_fields_from_graph_user(record)
        additional_data = {
            "email": email,
            "name": record.display_name,
            "user_principal_name": record.user_principal_name,
            "user_type": record.user_type,
        }

        user_id = await self._repository.get_user_id_by_third_party(
            ThirdPartyProvider.MICROSOFT,
            record.object_id,
        )

        if user_id:
            if dry_run:
                stats.updated += 1
                self._append_dry_run_action(
                    stats,
                    "update",
                    record,
                    email=email,
                    user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    preferred_name=preferred_name,
                )
                return
            await self._repository.update_directory_user_profile(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                preferred_name=preferred_name,
            )
            await self._repository.update_user_active_flag(user_id, record.account_enabled)
            await self._repository.upsert_auth_user_third_party(
                user_id=user_id,
                provider=ThirdPartyProvider.MICROSOFT,
                provider_uid=record.object_id,
                provider_tenant_id=tenant_id,
                additional_data=additional_data,
            )
            stats.updated += 1
            return

        existing = await self._repository.get_sensitive_by_email_without_profile(email)
        if existing:
            if dry_run:
                stats.linked += 1
                self._append_dry_run_action(
                    stats,
                    "link",
                    record,
                    email=email,
                    user_id=existing.id,
                    first_name=first_name,
                    last_name=last_name,
                    preferred_name=preferred_name,
                )
                return
            if not await self._repository.user_profile_exists(existing.id):
                await self._repository.create_user_profile(
                    user_id=existing.id,
                    first_name=first_name,
                    last_name=last_name,
                    preferred_name=preferred_name,
                )
            else:
                await self._repository.update_directory_user_profile(
                    user_id=existing.id,
                    first_name=first_name,
                    last_name=last_name,
                    preferred_name=preferred_name,
                )
            await self._repository.update_user_active_flag(existing.id, record.account_enabled)
            await self._repository.upsert_auth_user_third_party(
                user_id=existing.id,
                provider=ThirdPartyProvider.MICROSOFT,
                provider_uid=record.object_id,
                provider_tenant_id=tenant_id,
                additional_data=additional_data,
            )
            stats.linked += 1
            return

        if dry_run:
            stats.created += 1
            self._append_dry_run_action(
                stats,
                "create",
                record,
                email=email,
                first_name=first_name,
                last_name=last_name,
                preferred_name=preferred_name,
            )
            return

        new_user_id = uuid4()
        await self._repository.create_directory_user(
            user_id=new_user_id,
            email=email,
            verified=True,
            is_active=record.account_enabled,
            is_admin=False,
            account_kind=AccountKind.MEMBER.value,
            first_name=first_name,
            last_name=last_name,
            preferred_name=preferred_name,
        )
        await self._repository.upsert_auth_user_third_party(
            user_id=new_user_id,
            provider=ThirdPartyProvider.MICROSOFT,
            provider_uid=record.object_id,
            provider_tenant_id=tenant_id,
            additional_data=additional_data,
        )
        stats.created += 1


async def run_microsoft_user_sync(
    session: Session,
    user_repository: UserRepositoryPort,
    graph_provider: MicrosoftGraphProvider,
    *,
    dry_run: bool = False,
    filter_expr: Optional[str] = None,
    dry_run_output_dir: Optional[Path] = None,
) -> MicrosoftUserSyncStats:
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=user_repository,
        graph_provider=graph_provider,
    )
    stats = await service.run(
        dry_run=dry_run,
        filter_expr=filter_expr,
        dry_run_output_dir=dry_run_output_dir,
    )
    click.echo(
        click.style(
            "Microsoft user sync "
            f"(dry_run={dry_run}): fetched={stats.total_fetched}, "
            f"created={stats.created}, updated={stats.updated}, linked={stats.linked}, "
            f"skipped_no_email={stats.skipped_no_email}, "
            f"skipped_domain_mismatch={stats.skipped_domain_mismatch}, "
            f"skipped_not_real_person={stats.skipped_not_real_person}, "
            f"skipped_service_account={stats.skipped_service_account}",
            fg="green",
        )
    )
    if dry_run and stats.dry_run_output_dir:
        click.echo(
            click.style(
                f"Dry-run report written to {stats.dry_run_output_dir}",
                fg="cyan",
            )
        )
    if stats.errors:
        click.echo(click.style(f"Errors: {len(stats.errors)}", fg="red"))
        for message in stats.errors:
            click.echo(click.style(f"  - {message}", fg="red"))
    logger.info(
        "Microsoft user sync completed: fetched=%s created=%s updated=%s linked=%s",
        stats.total_fetched,
        stats.created,
        stats.updated,
        stats.linked,
    )
    return stats
