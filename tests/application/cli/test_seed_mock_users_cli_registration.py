"""
CLI wiring: seed-mock-users replaces the retired create-mock-user command.
"""

from portal.cli.main import cli


def test_seed_mock_users_command_is_registered():
    assert "seed-mock-users" in cli.commands


def test_create_mock_user_command_is_retired():
    assert "create-mock-user" not in cli.commands
