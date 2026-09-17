"""
Orchestration tests for init-all catalog bootstrap.
"""

import pytest

from portal.application.cli.init_all_service import InitAllService
from portal.cli.main import cli

CATALOG_STEP_NAMES = ("locales", "rbac", "system_settings", "positions", "target_audiences", "facility_rental", "legal_documents")


def _build_service(calls: list[str], *, fail_on: str | None = None) -> InitAllService:
    def make_step(name: str):
        async def step() -> None:
            calls.append(name)
            if name == fail_on:
                raise RuntimeError(f"{name} failed")

        return step

    def create_superuser() -> None:
        calls.append("create_superuser")

    return InitAllService(
        init_locales=make_step("locales"),
        init_rbac=make_step("rbac"),
        seed_system_settings=make_step("system_settings"),
        seed_positions=make_step("positions"),
        seed_target_audiences=make_step("target_audiences"),
        seed_facility_rental=make_step("facility_rental"),
        seed_legal_documents=make_step("legal_documents"),
        create_superuser=create_superuser,
    )


def test_init_all_runs_catalog_steps_then_superuser_in_order():
    calls: list[str] = []
    _build_service(calls).run()

    assert calls == [*CATALOG_STEP_NAMES, "create_superuser"]


def test_init_all_stops_before_later_steps_when_a_catalog_step_fails():
    calls: list[str] = []

    with pytest.raises(RuntimeError, match="rbac failed"):
        _build_service(calls, fail_on="rbac").run()

    assert calls == ["locales", "rbac"]
    assert "create_superuser" not in calls


def test_init_all_command_is_registered():
    assert "init-all" in cli.commands


def test_init_all_stops_before_later_steps_when_a_catalog_step_fails():
    calls: list[str] = []

    with pytest.raises(RuntimeError, match="rbac failed"):
        _build_service(calls, fail_on="rbac").run()

    assert calls == ["locales", "rbac"]
    assert "create_superuser" not in calls
