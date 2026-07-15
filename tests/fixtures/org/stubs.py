"""
Stub repositories for org application unit tests.
"""
from typing import Optional
from uuid import UUID

from portal.application.org.commands import PagesQueryCommand
from portal.application.org.results import (
    MinistryApprovalResult,
    MinistryDetailResult,
    MinistryListItemResult,
    MinistryMemberResult,
    MinistryTypeResult,
    TargetAudienceResult,
)
from portal.domain.org.catalog_codes import MINISTRY_TYPE_INTERNAL


class StubMinistryTypeRepository:
    """In-memory ministry type catalog stub."""

    def __init__(self, default_type_id: UUID | None = None):
        self.default_type_id = default_type_id or UUID("00000000-0000-4000-8000-000000000001")

    async def get_active_by_id(self, ministry_type_id: UUID) -> MinistryTypeResult | None:
        return MinistryTypeResult(id=ministry_type_id, code=MINISTRY_TYPE_INTERNAL)

    async def get_id_by_code(self, code: str) -> UUID | None:
        if code == MINISTRY_TYPE_INTERNAL:
            return self.default_type_id
        return None

    async def list_active(self, locale_id):
        return [MinistryTypeResult(id=self.default_type_id, code=MINISTRY_TYPE_INTERNAL, name="Internal")]


class StubTargetAudienceRepository:
    """In-memory target audience catalog stub."""

    def __init__(self, audiences: dict[UUID, TargetAudienceResult] | None = None):
        self.audiences = audiences or {}

    async def fetch_active_by_ids(self, audience_ids: list[UUID]) -> list[TargetAudienceResult]:
        return [self.audiences[audience_id] for audience_id in audience_ids if audience_id in self.audiences]

    async def list_active(self, locale_id):
        return list(self.audiences.values())

    async def list_for_ministry(self, ministry_id: UUID, locale_id):
        return []


class StubMinistryRepository:
    """In-memory org ministry stub."""

    def __init__(
        self,
        ministry_by_id: dict[UUID, MinistryDetailResult] | None = None,
        members_by_ministry: dict[UUID, list[MinistryMemberResult]] | None = None,
    ):
        self.ministry_by_id = ministry_by_id or {}
        self.members_by_ministry = members_by_ministry or {}
        self.insert_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.upsert_translation_calls: list[list] = []
        self.replace_members_calls: list[dict] = []
        self.upsert_schedules_calls: list[dict] = []
        self.upsert_target_audiences_calls: list[dict] = []
        self.insert_approval_calls: list[dict] = []
        self.update_approval_calls: list[dict] = []

    async def get_by_id(
        self,
        ministry_id: UUID,
        locale_id: Optional[UUID] = None,
        all_locales: bool = False,
    ) -> MinistryDetailResult | None:
        return self.ministry_by_id.get(ministry_id)

    async def insert_ministry(self, payload: dict) -> None:
        self.insert_calls.append(payload)

    async def update_ministry(self, ministry_id: UUID, values: dict) -> int:
        self.update_calls.append({"ministry_id": ministry_id, "values": values})
        return 1

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        return set(locale_ids)

    async def upsert_translations(self, rows: list) -> None:
        self.upsert_translation_calls.append(rows)

    async def list_members(self, ministry_id: UUID) -> list[MinistryMemberResult]:
        return self.members_by_ministry.get(ministry_id, [])

    async def replace_members(
        self,
        ministry_id: UUID,
        members: list[dict],
    ) -> None:
        self.replace_members_calls.append(
            dict(ministry_id=ministry_id, members=members)
        )

    async def upsert_schedules(self, ministry_id: UUID, rows: list[dict]) -> None:
        self.upsert_schedules_calls.append(dict(ministry_id=ministry_id, rows=rows))

    async def upsert_target_audiences(self, ministry_id: UUID, audience_ids: list[UUID]) -> None:
        self.upsert_target_audiences_calls.append(
            dict(ministry_id=ministry_id, audience_ids=audience_ids)
        )

    async def list_schedules(self, ministry_id: UUID):
        return []

    async def list_target_audiences(self, ministry_id: UUID, locale_id):
        return []

    async def insert_approval(self, payload: dict) -> None:
        self.insert_approval_calls.append(payload)

    async def update_approval(self, **kwargs) -> None:
        self.update_approval_calls.append(kwargs)

    async def fetch_pages(self, command: PagesQueryCommand, locale_id):
        return [], 0

    async def list_active(self, locale_id) -> list[MinistryListItemResult]:
        return []

    async def list_owned_active(self, user_id: UUID, locale_id) -> list[MinistryListItemResult]:
        return []

    async def fetch_approval_pages(self, command, locale_id):
        return [], 0

    async def fetch_approval_request_pages(self, command) -> tuple[list[MinistryApprovalResult], int]:
        return [], 0

    async def delete_hard(self, ministry_id):
        pass

    async def delete_soft(self, ministry_id, reason):
        pass

    async def restore_ministry(self, ministry_id):
        pass

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return False
