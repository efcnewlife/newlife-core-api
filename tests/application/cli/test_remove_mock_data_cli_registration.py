"""
CLI wiring: remove-mock-data hard-deletes Mock QA data seeded by seed-mock-users / seed-mock-data (#176).
"""

from portal.cli.main import cli


def test_remove_mock_data_command_is_registered():
    assert "remove-mock-data" in cli.commands
