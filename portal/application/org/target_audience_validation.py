"""
Target audience assignment validation helpers.
"""
from uuid import UUID

from portal.application.org.results import TargetAudienceResult
from portal.domain.org.catalog_codes import TARGET_AUDIENCE_ALL_AGES
from portal.exceptions.responses import BadRequestException


def validate_target_audience_ids(
    audience_ids: list[UUID],
    active_audiences: list[TargetAudienceResult],
) -> None:
    if not audience_ids:
        return
    active_by_id = {item.id: item for item in active_audiences}
    if len(active_by_id) != len(set(audience_ids)):
        raise BadRequestException(detail="Invalid or inactive target_audience_id")
    codes = [active_by_id[audience_id].code for audience_id in audience_ids]
    if TARGET_AUDIENCE_ALL_AGES in codes and len(codes) != 1:
        raise BadRequestException(detail="all_ages cannot be combined with other target audiences")
