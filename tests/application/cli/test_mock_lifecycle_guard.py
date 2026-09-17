"""
Tests for the Mock QA data lifecycle environment guard.
"""

import pytest

from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error


@pytest.mark.parametrize(
    ("is_prod", "is_dev", "force", "expect_blocked"),
    [
        (False, True, False, False),  # dev: always allowed
        (False, True, True, False),  # dev with --force: still allowed
        (False, False, False, True),  # staging without --force: blocked
        (False, False, True, False),  # staging with --force: allowed
        (True, False, False, True),  # production: blocked
        (True, False, True, True),  # production with --force: still blocked
    ],
)
def test_mock_lifecycle_environment_guard(is_prod: bool, is_dev: bool, force: bool, expect_blocked: bool):
    error = mock_lifecycle_environment_guard_error(is_prod=is_prod, is_dev=is_dev, force=force, command_name="seed-mock-users")

    assert (error is not None) is expect_blocked
    if error is not None:
        assert "seed-mock-users" in error


def test_mock_lifecycle_environment_guard_production_message_has_no_force_hint():
    error = mock_lifecycle_environment_guard_error(is_prod=True, is_dev=False, force=True, command_name="seed-mock-users")

    assert error is not None
    assert "--force" not in error
