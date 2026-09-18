"""
CLI wiring: seed-mock-users replaces the retired create-mock-user command.
The Mock QA lifecycle is the supported fixture path; seed-local-demo has no alias.
"""

from portal.cli.main import cli


def test_seed_mock_users_command_is_registered():
    assert "seed-mock-users" in cli.commands


def test_create_mock_user_command_is_retired():
    assert "create-mock-user" not in cli.commands


def test_seed_local_demo_command_is_retired():
    assert "seed-local-demo" not in cli.commands


def test_supported_mock_fixture_lifecycle_commands_remain_registered():
    assert "init-all" in cli.commands
    assert "seed-mock-users" in cli.commands
    assert "seed-mock-data" in cli.commands
    assert "remove-mock-data" in cli.commands
