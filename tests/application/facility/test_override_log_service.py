"""
OverrideLogService unit tests.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from portal.application.facility.commands import OverrideLogPagesQueryCommand
from portal.application.facility.override_log_service import OverrideLogService
from portal.application.facility.results import OverrideLogResult
from tests.fixtures.facility.stubs import StubOverrideLogRepository


@pytest.mark.asyncio
async def test_get_override_log_pages_maps_pagination():
    log_id = uuid4()
    items = [
        OverrideLogResult(
            id=log_id,
            facility_booking_id=uuid4(),
            overridden_by_id=uuid4(),
            facility_id=uuid4(),
            outcome="override_applied",
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    ]
    stub = StubOverrideLogRepository(items=items, total=1)
    service = OverrideLogService(stub)
    command = OverrideLogPagesQueryCommand(page=1, page_size=10)
    result = await service.get_override_log_pages(command)
    assert result.page == 1
    assert result.page_size == 10
    assert result.total == 1
    assert result.items[0].id == log_id
