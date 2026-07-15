"""
Map between org API serializers and application commands/results.
"""
from uuid import UUID

from portal.application.org.commands import (
    ApproveMinistryCommand,
    AssignPositionCommand,
    BulkIdsCommand,
    CreateMemberPersonCommand,
    CreateMinistryCommand,
    CreatePositionCommand,
    DeleteCommand,
    LinkMemberPersonCommand,
    MinistryApplicationCommand,
    MinistryMemberEntryCommand,
    MinistryScheduleCommand,
    OrgTranslationCommand,
    PagesQueryCommand,
    PositionTranslationCommand,
    RejectMinistryCommand,
    ReplaceMinistryMembersCommand,
    UpdateMemberPersonCommand,
    UpdateMinistryCommand,
    UpdatePositionCommand,
)
from portal.application.org.results import (
    AssignablePositionResult,
    CreateIdResult,
    MemberPersonDetailResult,
    MemberPersonPageResult,
    MinistryDetailResult,
    MinistryListResult,
    MinistryMemberResult,
    MinistryPageResult,
    MinistryScheduleResult,
    MinistryTypeListResult,
    MinistryTypeResult,
    TargetAudienceListResult,
    TargetAudienceResult,
    PositionDetailResult,
    PositionPageResult,
    PositionTranslationItemResult,
    TranslationItemResult,
)
from portal.domain.common.mixins import UUIDBaseModel
from portal.serializers.admin.v1.org.member_person import (
    AdminMemberPersonCreate,
    AdminMemberPersonDetail,
    AdminMemberPersonLink,
    AdminMemberPersonPages,
    AdminMemberPersonUpdate,
)
from portal.serializers.admin.v1.ministry import (
    AdminMinistryApplicationCreate,
    AdminMinistryApprove,
    AdminMinistryBulkAction,
    AdminMinistryCreate,
    AdminMinistryDetail,
    AdminMinistryList,
    AdminMinistryMemberInput,
    AdminMinistryMemberItem,
    AdminMinistryPages,
    AdminMinistryReject,
    AdminMinistryReplaceMembers,
    AdminMinistryScheduleInput,
    AdminMinistryScheduleItem,
    AdminMinistryUpdate,
)
from portal.serializers.admin.v1.ministry_catalog import (
    AdminMinistryTypeItem,
    AdminMinistryTypeList,
    AdminTargetAudienceItem,
    AdminTargetAudienceList,
)
from portal.serializers.admin.v1.org.position import (
    AdminAssignablePositionItem,
    AdminAssignablePositionList,
    AdminPositionAssign,
    AdminPositionBulkAction,
    AdminPositionCreate,
    AdminPositionDetail,
    AdminPositionPages,
    AdminPositionUpdate,
)
from portal.serializers.admin.v1.org.translation import (
    AdminOrgTranslationInput,
    AdminOrgTranslationItem,
    AdminPositionTranslationInput,
    AdminPositionTranslationItem,
)
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel


def pages_query_to_command(model: GenericQueryBaseModel) -> PagesQueryCommand:
    return PagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        keyword=model.keyword,
    )


def delete_model_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def bulk_action_to_command(model: AdminMinistryBulkAction | AdminPositionBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def _org_translation_commands(
    translations: list[AdminOrgTranslationInput] | None,
) -> list[OrgTranslationCommand] | None:
    if translations is None:
        return None
    return [
        OrgTranslationCommand(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
            schedule_note=item.schedule_note,
        )
        for item in translations
    ]


def _position_translation_commands(
    translations: list[AdminPositionTranslationInput] | None,
) -> list[PositionTranslationCommand] | None:
    if translations is None:
        return None
    return [
        PositionTranslationCommand(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
        )
        for item in translations
    ]


def _org_translation_items_to_api(items: list[TranslationItemResult]) -> list[AdminOrgTranslationItem]:
    return [
        AdminOrgTranslationItem(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
            schedule_note=item.schedule_note,
        )
        for item in items
    ]


def _position_translation_items_to_api(
    items: list[PositionTranslationItemResult],
) -> list[AdminPositionTranslationItem]:
    return [
        AdminPositionTranslationItem(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
        )
        for item in items
    ]


def _schedule_commands(schedules: list[AdminMinistryScheduleInput] | None) -> list[MinistryScheduleCommand] | None:
    if schedules is None:
        return None
    return [
        MinistryScheduleCommand(
            days_of_week=schedule.days_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            effective_from=schedule.effective_from,
            effective_to=schedule.effective_to,
            sequence=schedule.sequence,
        )
        for schedule in schedules
    ]


def _ministry_type_to_api(item: MinistryTypeResult | None) -> AdminMinistryTypeItem | None:
    if not item:
        return None
    return AdminMinistryTypeItem(id=item.id, code=item.code, name=item.name)


def _target_audiences_to_api(items: list[TargetAudienceResult]) -> list[AdminTargetAudienceItem]:
    return [
        AdminTargetAudienceItem(id=item.id, code=item.code, name=item.name)
        for item in items
    ]


def _schedules_to_api(items: list[MinistryScheduleResult]) -> list[AdminMinistryScheduleItem]:
    return [
        AdminMinistryScheduleItem(
            id=item.id,
            days_of_week=item.days_of_week,
            start_time=item.start_time,
            end_time=item.end_time,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            sequence=item.sequence,
        )
        for item in items
    ]


def _member_commands(members: list[AdminMinistryMemberInput]) -> list[MinistryMemberEntryCommand]:
    return [
        MinistryMemberEntryCommand(
            user_id=member.user_id,
            member_role=member.member_role,
            remark=member.remark,
            contact_email=member.contact_email,
        )
        for member in members
    ]


def _members_to_api(members: list[MinistryMemberResult]) -> list[AdminMinistryMemberItem]:
    return [
        AdminMinistryMemberItem(
            user_id=member.user_id,
            member_role=member.member_role,
            email=member.email,
            display_name=member.display_name,
            remark=member.remark,
            contact_email=member.contact_email,
        )
        for member in members
    ]


def create_id_result_to_api(result: CreateIdResult) -> UUIDBaseModel:
    return UUIDBaseModel(id=result.id)


def create_ministry_to_command(model: AdminMinistryCreate) -> CreateMinistryCommand:
    return CreateMinistryCommand(
        name=model.name,
        owner_position_id=model.owner_position_id,
        ministry_type_id=model.ministry_type_id,
        target_audience_ids=model.target_audience_ids or [],
        schedules=_schedule_commands(model.schedules) or [],
        has_priority_booking=model.has_priority_booking,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_org_translation_commands(model.translations),
    )


def update_ministry_to_command(model: AdminMinistryUpdate) -> UpdateMinistryCommand:
    return UpdateMinistryCommand(
        name=model.name,
        owner_position_id=model.owner_position_id,
        ministry_type_id=model.ministry_type_id,
        target_audience_ids=model.target_audience_ids,
        schedules=_schedule_commands(model.schedules),
        has_priority_booking=model.has_priority_booking,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_org_translation_commands(model.translations),
    )


def ministry_application_to_command(model: AdminMinistryApplicationCreate) -> MinistryApplicationCommand:
    return MinistryApplicationCommand(
        owner_position_id=model.owner_position_id,
        has_priority_booking=model.has_priority_booking,
        translations=_org_translation_commands(model.translations) or [],
        members=_member_commands(model.members),
    )


def replace_ministry_members_to_command(model: AdminMinistryReplaceMembers) -> ReplaceMinistryMembersCommand:
    return ReplaceMinistryMembersCommand(members=_member_commands(model.members))


def approve_ministry_to_command(model: AdminMinistryApprove) -> ApproveMinistryCommand:
    return ApproveMinistryCommand(comment=model.comment)


def reject_ministry_to_command(model: AdminMinistryReject) -> RejectMinistryCommand:
    return RejectMinistryCommand(rejection_reason=model.rejection_reason, comment=model.comment)


def ministry_detail_to_api(result: MinistryDetailResult) -> AdminMinistryDetail:
    return AdminMinistryDetail(
        id=result.id,
        name=result.name,
        status=result.status,
        owner_position_id=result.owner_position_id,
        ministry_type_id=result.ministry_type_id,
        ministry_type=_ministry_type_to_api(result.ministry_type),
        has_priority_booking=result.has_priority_booking,
        is_active=result.is_active,
        sequence=result.sequence,
        submitted_at=result.submitted_at,
        submitted_by_id=result.submitted_by_id,
        approved_at=result.approved_at,
        approved_by_id=result.approved_by_id,
        rejected_at=result.rejected_at,
        rejected_by_id=result.rejected_by_id,
        rejection_reason=result.rejection_reason,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
        translations=_org_translation_items_to_api(result.translations),
        members=_members_to_api(result.members),
        target_audiences=_target_audiences_to_api(result.target_audiences),
        schedules=_schedules_to_api(result.schedules),
    )


def ministry_page_to_api(result: MinistryPageResult) -> AdminMinistryPages:
    return AdminMinistryPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[ministry_detail_to_api(item) for item in result.items],
    )


def ministry_list_to_api(result: MinistryListResult) -> AdminMinistryList:
    from portal.serializers.admin.v1.ministry import AdminMinistryBase

    return AdminMinistryList(
        items=[
            AdminMinistryBase(
                id=item.id,
                name=item.name,
                status=item.status,
                has_priority_booking=item.has_priority_booking,
                is_active=item.is_active,
                ministry_type=_ministry_type_to_api(item.ministry_type),
                target_audiences=_target_audiences_to_api(item.target_audiences),
            )
            for item in result.items
        ]
    )


def ministry_type_list_to_api(result: MinistryTypeListResult) -> AdminMinistryTypeList:
    return AdminMinistryTypeList(
        items=[
            AdminMinistryTypeItem(id=item.id, code=item.code, name=item.name)
            for item in result.items
        ]
    )


def target_audience_list_to_api(result: TargetAudienceListResult) -> AdminTargetAudienceList:
    return AdminTargetAudienceList(
        items=[
            AdminTargetAudienceItem(id=item.id, code=item.code, name=item.name)
            for item in result.items
        ]
    )


def create_position_to_command(model: AdminPositionCreate) -> CreatePositionCommand:
    return CreatePositionCommand(
        code=model.code,
        team=model.team,
        office=model.office,
        can_own_ministry=model.can_own_ministry,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_position_translation_commands(model.translations),
    )


def update_position_to_command(model: AdminPositionUpdate) -> UpdatePositionCommand:
    return UpdatePositionCommand(
        team=model.team,
        office=model.office,
        can_own_ministry=model.can_own_ministry,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_position_translation_commands(model.translations),
    )


def assign_position_to_command(model: AdminPositionAssign) -> AssignPositionCommand:
    return AssignPositionCommand(user_id=model.user_id, start_at=model.start_at)


def position_detail_to_api(result: PositionDetailResult) -> AdminPositionDetail:
    return AdminPositionDetail(
        id=result.id,
        code=result.code,
        team=result.team,
        office=result.office,
        name=result.name,
        can_own_ministry=result.can_own_ministry,
        is_active=result.is_active,
        sequence=result.sequence,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
        translations=_position_translation_items_to_api(result.translations),
        current_user_id=result.current_user_id,
    )


def position_page_to_api(result: PositionPageResult) -> AdminPositionPages:
    return AdminPositionPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[position_detail_to_api(item) for item in result.items],
    )


def assignable_positions_to_api(items: list[AssignablePositionResult]) -> AdminAssignablePositionList:
    return AdminAssignablePositionList(
        items=[
            AdminAssignablePositionItem(
                id=item.id,
                code=item.code,
                team=item.team,
                office=item.office,
                name=item.name,
                incumbent_user_id=item.incumbent_user_id,
                incumbent_display_name=item.incumbent_display_name,
            )
            for item in items
        ]
    )


def create_member_person_to_command(model: AdminMemberPersonCreate) -> CreateMemberPersonCommand:
    return CreateMemberPersonCommand(legal_name=model.legal_name, user_id=model.user_id)


def update_member_person_to_command(model: AdminMemberPersonUpdate) -> UpdateMemberPersonCommand:
    return UpdateMemberPersonCommand(legal_name=model.legal_name)


def link_member_person_to_command(model: AdminMemberPersonLink) -> LinkMemberPersonCommand:
    return LinkMemberPersonCommand(user_id=model.user_id)


def member_person_detail_to_api(result: MemberPersonDetailResult) -> AdminMemberPersonDetail:
    return AdminMemberPersonDetail(
        id=result.id,
        legal_name=result.legal_name,
        user_id=result.user_id,
        email=result.email,
        display_name=result.display_name,
    )


def member_person_page_to_api(result: MemberPersonPageResult) -> AdminMemberPersonPages:
    return AdminMemberPersonPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[member_person_detail_to_api(item) for item in result.items],
    )
