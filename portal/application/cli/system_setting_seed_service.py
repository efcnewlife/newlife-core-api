"""
System setting seed use case for CLI (insert-if-missing).
"""

import json
from typing import NamedTuple

import click

from portal.domain.system.constants import FacilitySettingKey, SettingNamespace
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import SystemSetting


class _LegacyHoldHoursConversion(NamedTuple):
    skip_days_seed: bool
    converted_days: int | None


class SystemSettingSeedService:
    """Insert system settings when namespace+key is absent; never overwrite value."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, seed_rows: list[dict]) -> int:
        inserted = 0
        for row in seed_rows:
            existing_id = await (
                self._session.select(SystemSetting.id)
                .where(SystemSetting.namespace == row["namespace"])
                .where(SystemSetting.setting_key == row["setting_key"])
                .where(SystemSetting.is_deleted == False)
                .fetchval()
            )
            if existing_id:
                continue
            insert_row = {**row}
            if insert_row["setting_key"] == FacilitySettingKey.PENDING_PAYMENT_HOLD_DAYS.value:
                conversion = await self._legacy_hold_hours_conversion()
                if conversion.skip_days_seed:
                    continue
                if conversion.converted_days is not None:
                    insert_row["value"] = conversion.converted_days
            # asyncpg JSONB bind expects a JSON text string (e.g. '"America/Toronto"').
            insert_row["value"] = json.dumps(insert_row["value"])
            await self._session.insert(SystemSetting).values(**insert_row).execute()
            inserted += 1
        await self._session.commit()
        click.echo(click.style(f"System settings seeded. inserted={inserted} skipped={len(seed_rows) - inserted}", fg="bright_green"))
        logger.info("System setting seed completed. inserted=%s skipped=%s", inserted, len(seed_rows) - inserted)
        return inserted

    async def _legacy_hold_hours_conversion(self) -> _LegacyHoldHoursConversion:
        hours_value = await (
            self._session.select(SystemSetting.value)
            .where(SystemSetting.namespace == SettingNamespace.FACILITY.value)
            .where(SystemSetting.setting_key == FacilitySettingKey.PENDING_PAYMENT_HOLD_HOURS.value)
            .where(SystemSetting.is_deleted == False)
            .where(SystemSetting.is_active == True)
            .fetchval()
        )
        if hours_value is None:
            return _LegacyHoldHoursConversion(skip_days_seed=False, converted_days=None)
        hours = json.loads(hours_value) if isinstance(hours_value, str) else hours_value
        if isinstance(hours, bool) or not isinstance(hours, int) or hours < 1 or hours % 24 != 0:
            return _LegacyHoldHoursConversion(skip_days_seed=True, converted_days=None)
        return _LegacyHoldHoursConversion(skip_days_seed=False, converted_days=hours // 24)
